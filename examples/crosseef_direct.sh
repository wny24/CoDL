#!/usr/bin/env bash
# Run from the CoDL workspace with its main Python environment activated.
set -euo pipefail
PYTHON=${PYTHON:-python}
AGENT_PYTHON=$("$PYTHON" -c 'import sys; print(sys.executable)')
"$AGENT_PYTHON" - <<'PY'
import importlib.util
import sys
missing = [name for name in ('numpy', 'PIL', 'scipy', 'uni_robot_agent')
           if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit('Missing planner dependencies: ' + ', '.join(missing)
        + '\nInstall this checkout with the compute extra into ' + sys.executable
        + ' before starting an episode. See docs/crosseef.md.')
import numpy, PIL, scipy
print('Planner calculations:', sys.executable, flush=True)
PY
: "${UNI_ROBOT_AGENT_API_KEY:?Set UNI_ROBOT_AGENT_API_KEY in this terminal}"
exec "$AGENT_PYTHON" -m uni_robot_agent run \
  --integration crosseef --deploy local \
  --cache-dir "${UNI_ROBOT_AGENT_CACHE_DIR:-$PWD/.runtime-cache}" \
  --task "${TASK:-CanSortDual}" --seed "${SEED:-0}" --depth \
  --env-port "${ENV_PORT:-18792}" \
  --agent-python "$AGENT_PYTHON" \
  --model "${MODEL:-qwen3.8-flash}" \
  --provider-profile "${PROVIDER_PROFILE:-aliyun.chat_completions}" \
  --provider-url "${UNI_ROBOT_AGENT_PROVIDER_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}" \
  --reasoning-effort "${REASONING_EFFORT:-high}" \
  --context-policy identity --action-profile direct --no-sam3 \
  --output-dir "${OUTPUT_DIR:-$PWD/runs}" --monitor "$@"
