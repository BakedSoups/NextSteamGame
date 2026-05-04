#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:-nextsteamgame.com}"
EMAIL="${EMAIL:-}"
APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SERVER_NAME="${SERVER_NAME:-nextsteamgame}"
NGINX_CONF_PATH="/etc/nginx/sites-available/${SERVER_NAME}.conf"
NGINX_ENABLED_PATH="/etc/nginx/sites-enabled/${SERVER_NAME}.conf"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root or with sudo."
  exit 1
fi

if [[ ! -f "${APP_DIR}/docker-compose.yml" ]]; then
  echo "Could not find docker-compose.yml in APP_DIR=${APP_DIR}"
  exit 1
fi

install_base_packages() {
  apt-get update
  apt-get install -y ca-certificates curl gnupg git nginx ufw
}

install_docker() {
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi

  cat >/etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME}") stable
EOF

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable docker
  systemctl restart docker
}

install_certbot() {
  apt-get install -y certbot python3-certbot-nginx
}

configure_firewall() {
  ufw allow OpenSSH || true
  ufw allow 'Nginx Full' || true
  ufw --force enable
}

write_nginx_config() {
  cat >"${NGINX_CONF_PATH}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN};

    client_max_body_size 25m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

  rm -f /etc/nginx/sites-enabled/default
  ln -sf "${NGINX_CONF_PATH}" "${NGINX_ENABLED_PATH}"
  nginx -t
  systemctl reload nginx
}

write_local_env_defaults() {
  local env_file="${APP_DIR}/.env"
  touch "${env_file}"

  if ! grep -q '^NEXT_PUBLIC_API_BASE_URL=' "${env_file}"; then
    echo "NEXT_PUBLIC_API_BASE_URL=https://${DOMAIN}" >> "${env_file}"
  fi
}

issue_certificate() {
  if [[ -z "${EMAIL}" ]]; then
    echo "Skipping certbot because EMAIL is empty."
    return
  fi

  certbot --nginx --non-interactive --agree-tos -m "${EMAIL}" -d "${DOMAIN}" -d "www.${DOMAIN}" --redirect
}

grant_docker_group_access() {
  if [[ -n "${SUDO_USER:-}" ]]; then
    usermod -aG docker "${SUDO_USER}" || true
  fi
}

main() {
  install_base_packages
  install_docker
  install_certbot
  configure_firewall
  write_local_env_defaults
  write_nginx_config
  issue_certificate
  grant_docker_group_access

  cat <<EOF

Droplet setup complete.

App directory:
  ${APP_DIR}

Next steps:
  cd ${APP_DIR}
  docker compose up --build -d

If you ran this with sudo, re-login once before using Docker without sudo.
EOF
}

main "$@"
