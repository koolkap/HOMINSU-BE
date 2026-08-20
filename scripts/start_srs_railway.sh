#!/bin/sh
set -eu

: "${SRS_HOOK_BASE_URL:?SRS_HOOK_BASE_URL must be set to the Backend private URL, for example http://backend.railway.internal:8000/api/v1/srs}"

case "$SRS_HOOK_BASE_URL" in
    http://*|https://*) ;;
    *)
        echo "SRS_HOOK_BASE_URL must start with http:// or https://" >&2
        exit 1
        ;;
esac

template=/opt/hominsu/srs.conf.template
config=/usr/local/srs/conf/srs.conf

# The Railway private URL contains ordinary URL characters. Escape the
# replacement value before using it with sed so the generated configuration
# remains valid if a custom private hostname is selected.
escaped_hook=$(printf '%s' "$SRS_HOOK_BASE_URL" | sed 's/[\\&|]/\\&/g')
sed "s|__SRS_HOOK_BASE_URL__|$escaped_hook|g" "$template" > "$config"

exec /usr/local/srs/objs/srs -c "$config"
