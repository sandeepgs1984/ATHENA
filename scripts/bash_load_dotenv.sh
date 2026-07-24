# Safe .env loader for bash scripts (no expansion of $ in values).
# Usage: source this file, then: athena_load_dotenv "/path/to/.env"
#
# Why: bcrypt hashes look like $2b$12$… — `source .env` under `set -u` fails
# with "unbound variable" and corrupts the hash even without -u.

athena_load_dotenv() {
  local env_file="$1"
  local line key val

  [[ -f "$env_file" ]] || return 0

  while IFS= read -r line || [[ -n "$line" ]]; do
    # trim CR (Windows) and leading/trailing whitespace
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue

    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
      # strip one layer of matching quotes
      if [[ "$val" =~ ^\"(.*)\"$ ]]; then
        val="${BASH_REMATCH[1]}"
      elif [[ "$val" =~ ^\'(.*)\'$ ]]; then
        val="${BASH_REMATCH[1]}"
      fi
      export "${key}=${val}"
    fi
  done < "$env_file"
}
