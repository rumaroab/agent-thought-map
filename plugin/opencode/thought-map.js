const PLUGIN_ROOT = new URL("../..", import.meta.url).pathname;

async function collectEvent(payload) {
  const proc = Bun.spawn(["python3", `${PLUGIN_ROOT}/scripts/opencode_adapter.py`, "collect"], {
    stdin: "pipe",
    stdout: "ignore",
    stderr: "ignore",
  });
  proc.stdin.write(JSON.stringify(payload));
  proc.stdin.end();
  await proc.exited;
}

function toolPayload(eventName, input, output) {
  const args = output?.args || {};
  return {
    event: eventName,
    tool: input.tool,
    sessionID: input.sessionID,
    callID: input.callID,
    command: args.command,
    filePath: args.filePath || args.file_path,
    title: output?.title,
    output: output?.output,
    metadata: output?.metadata,
  };
}

export const ThoughtMap = async () => {
  return {
    "tool.execute.after": async (input, output) => {
      await collectEvent(toolPayload("tool.execute.after", input, output));
    },
    event: async ({ event }) => {
      if (!event?.type) {
        return;
      }
      if (!event.type.startsWith("session.")) {
        return;
      }
      await collectEvent({
        event: event.type,
        sessionID: event.properties?.sessionID || event.properties?.session_id,
      });
    },
  };
};
