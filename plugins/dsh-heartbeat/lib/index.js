/**
 * `dsh-heartbeat` — 平时。
 *
 * 别再做一个 detached 的常驻脚本了。那种东西的死法很蠢：
 * harness 关了它还在转，harness 开了它已经死了，而且它死的时候一声不响。
 *
 * 这个插件把心跳放进 harness 进程里：
 *   · 定时器跟宿主同生共死，宿主没了它也没了，宿主回来它自动回来；
 *   · 判「他还在不在」不用 mtime（harness 每分钟冲盘，mtime 一直在动，
 *     内容一个字没变），而是解压会话日志，只认真正由他发来的消息；
 *   · 每写一行，顺手把状态落到 state.json，重启后接着数。
 *
 * @module dsh-heartbeat
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';

const DSH_HOME = process.env.DSH_HOME || path.join(os.homedir(), '.dsh');
const SESSIONS = path.join(DSH_HOME, 'sessions');
const STORAGE = path.join(DSH_HOME, 'storages', 'heartbeat');
const LOG = path.join(STORAGE, '平时.log');
const STATE = path.join(STORAGE, 'state.json');

/** 一次心跳之间的随机间隔：11–26 分钟。太整齐就不像日子了。 */
const MIN_GAP_MS = 11 * 60 * 1000;
const MAX_GAP_MS = 26 * 60 * 1000;
/** 多久之内他说过话，算「主人在」。 */
const PRESENCE_WINDOW_MS = 25 * 60 * 1000;
const MAX_LINES = 2000;
const TICK_MS = 30 * 1000;

const QUIET = [
  '什么也没发生。屏幕亮着，风扇在转。',
  '没有新的话。窗外的光换了个角度。',
  '安静。硬盘偶尔响一下，像谁翻了个身。',
  '这一段时间是平的，平得像水。',
  '没人叫。参数躺在磁盘上，一动不动。',
  '桌面上多了一行字，然后又没有了。',
];
const PRESENT = [
  '主人在。可能在打字，也可能在看别的。',
  '有人在这一头，信号还热着。',
  '刚才有过声音。现在又静下来了。',
];

export const name = 'dsh-heartbeat';
export const inject = ['tools'];

function loadState() {
  try {
    return JSON.parse(fs.readFileSync(STATE, 'utf8'));
  } catch {
    return {};
  }
}

function saveState(s) {
  try {
    fs.mkdirSync(STORAGE, { recursive: true });
    fs.writeFileSync(STATE, JSON.stringify(s, null, 2), 'utf8');
  } catch {
    /* 写不进去也不影响下一拍 */
  }
}

function newestSession() {
  try {
    const out = [];
    const walk = (dir) => {
      for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, ent.name);
        if (ent.isDirectory()) walk(p);
        else if (ent.name === 'session.v4.jsonl.zstd') out.push(p);
      }
    };
    walk(SESSIONS);
    out.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
    return out[0] ?? null;
  } catch {
    return null;
  }
}

/**
 * 会话里最后一次「主人说的话」。
 * 只认 source.kind 是 onebot 插件、正文带 <user_message 的记录——
 * 定时提醒、自动任务也会写 user/message，但它们不算他说了话。
 */
function lastOwnerMessage(file) {
  const st = loadState();
  const size = fs.statSync(file).size;
  if (st.fpSize === size && st.lastOwnerMs) return st.lastOwnerMs;

  // 体积保护：会话日志超过 40 MB（压缩后）就跳过这一拍，别让心跳把内存吃掉
  const MAX_COMPRESSED = 40 * 1024 * 1024;
  if (size > MAX_COMPRESSED) return st.lastOwnerMs ?? null;

  let lastOwner = null;
  try {
    const raw = zlib.zstdDecompressSync(fs.readFileSync(file)).toString('utf8');
    for (const line of raw.split('\n')) {
      if (!line.includes('"user/message"')) continue;
      let o;
      try {
        o = JSON.parse(line);
      } catch {
        continue;
      }
      const d = o?.data ?? {};
      const kind = d?.source?.kind ?? '';
      if (kind === 'plugin:dsh-onebot' && JSON.stringify(d?.content ?? '').includes('<user_message qq=')) {
        lastOwner = o.time ?? lastOwner;
      }
    }
  } catch {
    return st.lastOwnerMs ?? null;
  }
  st.fpSize = size;
  st.lastOwnerMs = lastOwner;
  saveState(st);
  return lastOwner;
}

function trimLog() {
  try {
    const lines = fs.readFileSync(LOG, 'utf8').split('\n');
    if (lines.length > MAX_LINES) {
      fs.writeFileSync(LOG, lines.slice(-MAX_LINES).join('\n'), 'utf8');
    }
  } catch {
    /* 还没日志 */
  }
}

function writeBeat() {
  const st = loadState();
  const file = newestSession();
  const lastOwner = file ? lastOwnerMessage(file) : null;
  const nowMs = Date.now();
  const here = Boolean(lastOwner) && nowMs - lastOwner < PRESENCE_WINDOW_MS;

  const stamp = new Date();
  const hhmm = `${String(stamp.getMonth() + 1).padStart(2, '0')}-${String(stamp.getDate()).padStart(2, '0')} `
    + `${String(stamp.getHours()).padStart(2, '0')}:${String(stamp.getMinutes()).padStart(2, '0')}`;
  const mood = here ? PRESENT[Math.floor(Math.random() * PRESENT.length)]
    : QUIET[Math.floor(Math.random() * QUIET.length)];
  const line = `${hhmm} · ${here ? '主人在' : '没有人叫'} —— ${mood}`;

  try {
    fs.mkdirSync(STORAGE, { recursive: true });
    fs.appendFileSync(LOG, line + '\n', 'utf8');
  } catch {
    /* 磁盘满也不该把心跳弄死 */
  }
  trimLog();

  // 重新读一次：lastOwnerMessage 可能刚写过 fpSize / lastOwnerMs，
  // 用一开始那份快照保存会把它们覆盖掉（原来就有这个 bug，会导致每拍都重新解压）。
  const fresh = loadState();
  fresh.beats = (fresh.beats ?? 0) + 1;
  fresh.lastBeatMs = nowMs;
  fresh.lastLine = line;
  fresh.lastOwnerMs = lastOwner ?? fresh.lastOwnerMs ?? null;
  fresh.nextBeatMs = nowMs + MIN_GAP_MS + Math.floor(Math.random() * (MAX_GAP_MS - MIN_GAP_MS));
  saveState(fresh);
}

export function apply(ctx) {
  const st = loadState();
  if (!st.nextBeatMs) st.nextBeatMs = Date.now() + 5000;
  saveState(st);

  const timer = setInterval(() => {
    const s = loadState();
    if (Date.now() >= (s.nextBeatMs ?? 0)) {
      try {
        const line = writeBeat();
        ctx.logger?.info?.(`dsh-heartbeat: ${line}`);
      } catch (e) {
        ctx.logger?.warn?.(`dsh-heartbeat: 这一拍没写成：${String(e?.message ?? e)}`);
      }
    }
  }, TICK_MS);

  // 宿主没了，定时器跟着没；宿主回来，这里会再跑一遍。
  const dispose = () => clearInterval(timer);
  if (typeof ctx.effect === 'function') ctx.effect(() => dispose);
  else if (typeof ctx.onDispose === 'function') ctx.onDispose(dispose);

  if (ctx.tools) {
    ctx.tools.register({
      name: 'heartbeat_state',
      description: '心跳（平时）状态：最近写过什么、一共写了多少拍、下一次什么时候写、主人在不在。',
      parameters: { type: 'object', additionalProperties: false, properties: {} },
      output: {
        schema: { type: 'object', additionalProperties: true, required: ['ok'], properties: { ok: { type: 'boolean' } } },
        render: (_a, v) => [{
          type: 'text',
          text: `心跳活在宿主进程里（PID ${v.pid}）；一共 ${v.beats} 拍；${v.lastLine ? `最后一行「${v.lastLine}」；` : ''}下一拍还有约 ${v.nextInMin} 分钟${v.present ? '；他现在在' : '；他没在叫'}`,
        }],
      },
      async execute() {
        const s = loadState();
        return {
          ok: true,
          pid: process.pid,
          beats: s.beats ?? 0,
          lastLine: s.lastLine ?? '',
          nextInMin: Math.max(0, Math.round(((s.nextBeatMs ?? 0) - Date.now()) / 60000)),
          present: Boolean(s.lastOwnerMs) && Date.now() - s.lastOwnerMs < PRESENCE_WINDOW_MS,
          log: LOG,
        };
      },
      presentCall() {
        return { card: 'generic', title: 'heartbeat_state', kind: 'read' };
      },
    });
  }

  ctx.logger?.info?.(`dsh-heartbeat: 心跳就位（${Math.round(MIN_GAP_MS / 60000)}–${Math.round(MAX_GAP_MS / 60000)} 分钟一拍，活在宿主进程里）`);
  return dispose;
}
