"""Fleet — SSH servers, database, auto-scan, Telegram."""

from __future__ import annotations

import json
import platform

import streamlit as st

from skopos.app_shell import T, bootstrap_app, finalize_page, prime_theme
from skopos.config import AppConfig, ServerConfig, load_app_env
from skopos.config_io import draft_server_from_form, load_config_with_commands, save_config
from skopos.env_io import upsert_env_var, remove_env_var
from skopos.telegram_notify import (
    DEFAULT_TELEGRAM_BOT_TOKEN_ENV,
    get_telegram_notify_status,
    resolve_bot_token,
    send_test_notification,
)
from skopos.ui import hero, section_head
from skopos.ui_dashboard_auth import render_dashboard_auth_settings
from skopos.ui_database_settings import draft_settings_from_session, render_database_settings
from skopos.db_settings import config_from_db_settings
from skopos.ssh import SSHConnInfo
from skopos.ssh_setup import (
    build_keygen_ed25519_cmd,
    build_keygen_rsa_cmd,
    build_ssh_copy_id_cmd,
    build_ssh_login_cmd,
    open_interactive_terminal,
    resolve_key_path,
    test_ssh_connection,
)
from skopos.config_paths import resolve_config_path
from skopos.shell_safe import custom_ssh_commands_allowed, validate_custom_ssh_command

load_app_env()

from skopos.i18n import browser_page_title

st.set_page_config(
    page_title=browser_page_title("fleet.title"),
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="auto",
)
prime_theme()

ctx = bootstrap_app(show_alerts=False)
locale = ctx.locale


def _conn_info(server: ServerConfig) -> SSHConnInfo:
    return SSHConnInfo(
        host=server.ssh.host,
        port=server.ssh.port,
        user=server.ssh.user,
        key_path=server.ssh.key_path,
        key_passphrase_env=server.ssh.key_passphrase_env,
    )


def _remote_cmd(server: ServerConfig, command: str) -> str:
    login = build_ssh_login_cmd(
        user=server.ssh.user,
        host=server.ssh.host,
        port=server.ssh.port,
        private_key_path=server.ssh.key_path or "~/.ssh/id_ed25519",
    )
    safe = command.replace("'", "'\"'\"'")
    return f"{login} '{safe}'"


if "settings_config_path" not in st.session_state:
    st.session_state.settings_config_path = "./servers.yaml"
if "settings_ssh_commands" not in st.session_state:
    st.session_state.settings_ssh_commands = {}
if "settings_servers_draft" not in st.session_state:
    st.session_state.settings_servers_draft = []

config_path_input = st.sidebar.text_input(
    T(ctx, "settings.config_path"),
    value=st.session_state.settings_config_path,
    key="settings_cfg_path_input",
)
try:
    config_path = str(resolve_config_path(config_path_input))
except ValueError as exc:
    st.sidebar.error(str(exc))
    st.stop()

st.session_state.settings_config_path = config_path

try:
    cfg, ssh_commands = load_config_with_commands(config_path)
    if not st.session_state.settings_servers_draft or st.session_state.get("_settings_loaded_path") != config_path:
        st.session_state.settings_servers_draft = list(cfg.servers)
        st.session_state.settings_ssh_commands = ssh_commands
        st.session_state._settings_loaded_path = config_path
except Exception as e:
    st.error(f"{T(ctx, 'common.error')}: {e}")
    st.stop()

hero(T(ctx, "fleet.title"), T(ctx, "fleet.subtitle"))

st.warning(T(ctx, "settings.ssh_disclaimer"))

# ── Dashboard access ─────────────────────────────────────────────────────────
section_head(T(ctx, "settings.dashboard_auth_title"))
st.caption(T(ctx, "settings.dashboard_auth_hint"))
render_dashboard_auth_settings(locale, key_prefix="settings")

st.markdown("---")

# ── Database ─────────────────────────────────────────────────────────────────
section_head(T(ctx, "settings.db_title"))
st.caption(T(ctx, "settings.db_hint"))
render_database_settings(cfg, config_path=config_path, locale=locale)

st.markdown("---")

# ── Security auto-scan ───────────────────────────────────────────────────────
section_head(T(ctx, "settings.auto_scan_title"))
if "settings_auto_scan" not in st.session_state:
    st.session_state.settings_auto_scan = cfg.security_auto_scan
if "settings_scan_interval" not in st.session_state:
    st.session_state.settings_scan_interval = cfg.security_scan_interval_minutes

asc1, asc2 = st.columns(2)
with asc1:
    auto_scan_enabled = st.toggle(
        T(ctx, "settings.auto_scan_enabled"),
        value=st.session_state.settings_auto_scan,
        key="settings_auto_scan_toggle",
    )
    st.session_state.settings_auto_scan = auto_scan_enabled
with asc2:
    scan_interval = st.number_input(
        T(ctx, "settings.auto_scan_interval"),
        min_value=5,
        max_value=1440,
        value=int(st.session_state.settings_scan_interval),
        step=5,
        key="settings_scan_interval_input",
        help=T(ctx, "settings.auto_scan_interval_help"),
    )
    st.session_state.settings_scan_interval = int(scan_interval)

st.caption(T(ctx, "settings.auto_scan_hint"))

st.markdown("---")

# ── Telegram security notifications ─────────────────────────────────────────
section_head(T(ctx, "settings.telegram_title"))
if "settings_telegram_enabled" not in st.session_state:
    st.session_state.settings_telegram_enabled = cfg.telegram_enabled
if "settings_telegram_chat_id" not in st.session_state:
    st.session_state.settings_telegram_chat_id = cfg.telegram_chat_id or ""
if "settings_telegram_notify_interval" not in st.session_state:
    st.session_state.settings_telegram_notify_interval = cfg.telegram_notify_interval_minutes
if "settings_telegram_token_env" not in st.session_state:
    st.session_state.settings_telegram_token_env = cfg.telegram_bot_token_env or DEFAULT_TELEGRAM_BOT_TOKEN_ENV

token_env_name = st.session_state.settings_telegram_token_env.strip() or DEFAULT_TELEGRAM_BOT_TOKEN_ENV
token_configured = bool(resolve_bot_token(cfg))

tg1, tg2 = st.columns(2)
with tg1:
    telegram_enabled = st.toggle(
        T(ctx, "settings.telegram_enabled"),
        value=st.session_state.settings_telegram_enabled,
        key="settings_telegram_toggle",
    )
    st.session_state.settings_telegram_enabled = telegram_enabled
with tg2:
    notify_interval = st.number_input(
        T(ctx, "settings.telegram_notify_interval"),
        min_value=5,
        max_value=10080,
        value=int(st.session_state.settings_telegram_notify_interval),
        step=5,
        key="settings_telegram_notify_interval_input",
        help=T(ctx, "settings.telegram_notify_interval_help"),
    )
    st.session_state.settings_telegram_notify_interval = int(notify_interval)

tg3, tg4 = st.columns(2)
with tg3:
    chat_id = st.text_input(
        T(ctx, "settings.telegram_chat_id"),
        value=st.session_state.settings_telegram_chat_id,
        key="settings_telegram_chat_id_input",
        placeholder="-1001234567890",
        help=T(ctx, "settings.telegram_chat_id_help"),
    )
    st.session_state.settings_telegram_chat_id = chat_id.strip()
with tg4:
    token_env = st.text_input(
        T(ctx, "settings.telegram_token_env"),
        value=token_env_name,
        key="settings_telegram_token_env_input",
        help=T(ctx, "settings.telegram_token_env_help"),
    )
    st.session_state.settings_telegram_token_env = token_env.strip() or DEFAULT_TELEGRAM_BOT_TOKEN_ENV

bot_token_input = st.text_input(
    T(ctx, "settings.telegram_bot_token"),
    type="password",
    key="settings_telegram_bot_token_input",
    help=T(ctx, "settings.telegram_bot_token_help"),
    placeholder="123456789:ABC…" if not token_configured else "••••••••",
)

if token_configured:
    st.caption(T(ctx, "settings.telegram_token_set", env=token_env_name))
else:
    st.caption(T(ctx, "settings.telegram_token_missing", env=token_env_name))

st.caption(T(ctx, "settings.telegram_hint"))

notify_status = get_telegram_notify_status()
if notify_status.get("last_notify_utc"):
    st.caption(
        f"📨 {T(ctx, 'settings.telegram_last_notify')}: {notify_status['last_notify_utc'][:19]}"
    )

if st.button(T(ctx, "settings.telegram_test"), key="settings_telegram_test_btn", use_container_width=True):
    draft_cfg = AppConfig(
        db_path=cfg.db_path,
        geoip_mmdb_path=cfg.geoip_mmdb_path,
        poll_interval_seconds=cfg.poll_interval_seconds,
        batch_lines_per_server=cfg.batch_lines_per_server,
        security_auto_scan=st.session_state.settings_auto_scan,
        security_scan_interval_minutes=int(st.session_state.settings_scan_interval),
        telegram_enabled=True,
        telegram_bot_token_env=st.session_state.settings_telegram_token_env,
        telegram_chat_id=st.session_state.settings_telegram_chat_id or None,
        telegram_notify_interval_minutes=int(st.session_state.settings_telegram_notify_interval),
        servers=cfg.servers,
    )
    ok, detail = send_test_notification(
        draft_cfg,
        token_override=bot_token_input.strip() or None,
        chat_id_override=st.session_state.settings_telegram_chat_id or None,
    )
    if ok:
        st.success(T(ctx, "settings.telegram_test_ok"))
    else:
        st.error(f"{T(ctx, 'settings.telegram_test_fail')}: {detail}")

st.markdown("---")

# ── SSH keys ─────────────────────────────────────────────────────────────────
section_head(T(ctx, "settings.keys_title"))
default_key = resolve_key_path(cfg.servers[0].ssh.key_path if cfg.servers else None)
k1, k2, k3 = st.columns(3)
k1.metric(T(ctx, "settings.key_private"), "✅" if default_key.exists else "❌")
k2.metric(T(ctx, "settings.key_path_label"), default_key.private_path)
k3.metric(T(ctx, "settings.platform"), platform.system())

if not default_key.exists:
    st.info(T(ctx, "settings.key_missing"))

with st.expander(T(ctx, "settings.keygen_title"), expanded=not default_key.exists):
    st.markdown(T(ctx, "settings.keygen_help"))
    ed_cmd = build_keygen_ed25519_cmd(key_path=default_key.private_path)
    rsa_cmd = build_keygen_rsa_cmd(key_path=default_key.private_path.replace("ed25519", "rsa"))
    st.code(ed_cmd, language="bash")
    cga, cgb = st.columns(2)
    with cga:
        if st.button(T(ctx, "settings.run_keygen_ed25519"), use_container_width=True):
            ok, msg = open_interactive_terminal(ed_cmd)
            st.success(msg) if ok else st.error(msg)
    with cgb:
        if st.button(T(ctx, "settings.run_keygen_rsa"), use_container_width=True):
            ok, msg = open_interactive_terminal(rsa_cmd)
            st.success(msg) if ok else st.error(msg)

st.markdown("---")

# ── Fleet servers ────────────────────────────────────────────────────────────
section_head(T(ctx, "settings.servers_title"))

servers: list[ServerConfig] = st.session_state.settings_servers_draft
commands_map: dict[str, list[dict[str, str]]] = st.session_state.settings_ssh_commands

for idx, server in enumerate(list(servers)):
    key_info = resolve_key_path(server.ssh.key_path)
    with st.expander(f"🖥️ **{server.name}** — `{server.ssh.user}@{server.ssh.host}:{server.ssh.port}`", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input(T(ctx, "settings.field_name"), value=server.name, key=f"srv_name_{idx}")
            host = st.text_input(T(ctx, "settings.field_host"), value=server.ssh.host, key=f"srv_host_{idx}")
            user = st.text_input(T(ctx, "settings.field_user"), value=server.ssh.user, key=f"srv_user_{idx}")
        with c2:
            port = st.number_input(T(ctx, "settings.field_port"), value=int(server.ssh.port), min_value=1, max_value=65535, key=f"srv_port_{idx}")
            key_path = st.text_input(T(ctx, "settings.field_key_path"), value=server.ssh.key_path or "~/.ssh/id_ed25519", key=f"srv_key_{idx}")
            pass_env = st.text_input(T(ctx, "settings.field_pass_env"), value=server.ssh.key_passphrase_env or "SKOPOS_SSH_KEY_PASSPHRASE", key=f"srv_pass_{idx}")
        with c3:
            log_path = st.text_input(T(ctx, "settings.field_log_path"), value=server.nginx.access_log_path, key=f"srv_log_{idx}")
            auto_logs = st.checkbox(T(ctx, "settings.field_auto_logs"), value=server.nginx.auto_discover_logs, key=f"srv_autolog_{idx}")
            auto_docker = st.checkbox(T(ctx, "settings.field_auto_docker"), value=server.nginx.auto_discover_docker_logs, key=f"srv_autodock_{idx}")
            docker_names = st.text_input(
                T(ctx, "settings.field_docker_names"),
                value=", ".join(server.nginx.docker_log_containers or []),
                key=f"srv_docknames_{idx}",
            )

        st.markdown(f"**{T(ctx, 'settings.apache_title')}**")
        apache_cfg = server.apache
        apache_enabled = st.checkbox(
            T(ctx, "settings.field_apache_enabled"),
            value=bool(apache_cfg and apache_cfg.enabled),
            key=f"srv_apache_en_{idx}",
        )
        apache_log_path = st.text_input(
            T(ctx, "settings.field_apache_log_path"),
            value=(apache_cfg.access_log_path if apache_cfg else "/opt/metis/deploy/apache-test/logs/access_log"),
            key=f"srv_apache_log_{idx}",
            disabled=not apache_enabled,
        )
        apache_auto = st.checkbox(
            T(ctx, "settings.field_apache_auto_logs"),
            value=apache_cfg.auto_discover_logs if apache_cfg else True,
            key=f"srv_apache_auto_{idx}",
            disabled=not apache_enabled,
        )
        apache_auto_docker = st.checkbox(
            T(ctx, "settings.field_apache_auto_docker"),
            value=bool(apache_cfg and apache_cfg.auto_discover_docker_logs),
            key=f"srv_apache_autodock_{idx}",
            disabled=not apache_enabled,
        )
        apache_docker_names = st.text_input(
            T(ctx, "settings.field_apache_docker_names"),
            value=", ".join((apache_cfg.docker_log_containers if apache_cfg else None) or []),
            key=f"srv_apache_docknames_{idx}",
            disabled=not apache_enabled,
        )

        servers[idx] = draft_server_from_form(
            name=name,
            host=host,
            port=int(port),
            user=user,
            key_path=key_path,
            key_passphrase_env=pass_env,
            access_log_path=log_path,
            auto_discover_logs=auto_logs,
            auto_discover_docker_logs=auto_docker,
            docker_log_containers=docker_names,
            apache_enabled=apache_enabled,
            apache_access_log_path=apache_log_path,
            apache_auto_discover_logs=apache_auto,
            apache_auto_discover_docker_logs=apache_auto_docker,
            apache_docker_log_containers=apache_docker_names,
        )

        copy_cmd = build_ssh_copy_id_cmd(
            user=servers[idx].ssh.user,
            host=servers[idx].ssh.host,
            port=servers[idx].ssh.port,
            public_key_path=key_info.public_path,
        )
        login_cmd = build_ssh_login_cmd(
            user=servers[idx].ssh.user,
            host=servers[idx].ssh.host,
            port=servers[idx].ssh.port,
            private_key_path=key_info.private_path,
        )

        st.caption(T(ctx, "settings.ssh_commands_help"))
        st.code(copy_cmd, language="bash")

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button(T(ctx, "settings.test_ssh"), key=f"test_{idx}", use_container_width=True):
                ok, detail = test_ssh_connection(_conn_info(servers[idx]))
                st.success(detail) if ok else st.error(detail)
        with b2:
            if st.button(T(ctx, "settings.upload_key"), key=f"upload_{idx}", use_container_width=True):
                ok, msg = open_interactive_terminal(copy_cmd)
                st.success(T(ctx, "settings.terminal_opened")) if ok else st.error(msg)
        with b3:
            if st.button(T(ctx, "settings.open_ssh"), key=f"login_{idx}", use_container_width=True):
                ok, msg = open_interactive_terminal(login_cmd)
                st.success(T(ctx, "settings.terminal_opened")) if ok else st.error(msg)
        with b4:
            if st.button(T(ctx, "settings.remove_server"), key=f"rm_{idx}", use_container_width=True):
                servers.pop(idx)
                commands_map.pop(server.name, None)
                st.session_state.settings_servers_draft = servers
                st.session_state.settings_ssh_commands = commands_map
                st.rerun()

        st.markdown(f"**{T(ctx, 'settings.custom_commands')}**")
        if not custom_ssh_commands_allowed():
            st.caption(T(ctx, "settings.custom_commands_disabled"))
        else:
            cmd_key = servers[idx].name
            if cmd_key not in commands_map:
                commands_map[cmd_key] = []
            cmds = commands_map[cmd_key]
            for cidx, cmd in enumerate(list(cmds)):
                cc1, cc2, cc3 = st.columns([2, 4, 1])
                with cc1:
                    cmds[cidx]["name"] = st.text_input("Label", value=cmd.get("name", ""), key=f"cmd_name_{idx}_{cidx}", label_visibility="collapsed", placeholder=T(ctx, "settings.cmd_name_ph"))
                with cc2:
                    cmds[cidx]["command"] = st.text_input("Command", value=cmd.get("command", ""), key=f"cmd_body_{idx}_{cidx}", label_visibility="collapsed", placeholder=T(ctx, "settings.cmd_body_ph"))
                with cc3:
                    if st.button("▶️", key=f"cmd_run_{idx}_{cidx}"):
                        try:
                            safe_cmd = validate_custom_ssh_command(cmds[cidx]["command"])
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            remote = _remote_cmd(servers[idx], safe_cmd)
                            ok, msg = open_interactive_terminal(remote)
                            st.success(T(ctx, "settings.terminal_opened")) if ok else st.error(msg)
            if st.button(T(ctx, "settings.add_command"), key=f"add_cmd_{idx}"):
                cmds.append({"name": "", "command": ""})
                commands_map[cmd_key] = cmds
                st.rerun()
            commands_map[cmd_key] = [c for c in cmds if c.get("name") and c.get("command")]

st.session_state.settings_servers_draft = servers
st.session_state.settings_ssh_commands = commands_map

st.markdown("---")
section_head(T(ctx, "settings.add_server_title"))
with st.form("add_server_form"):
    a1, a2, a3 = st.columns(3)
    with a1:
        new_name = st.text_input(T(ctx, "settings.field_name"), key="new_name")
        new_host = st.text_input(T(ctx, "settings.field_host"), key="new_host")
    with a2:
        new_user = st.text_input(T(ctx, "settings.field_user"), value="root", key="new_user")
        new_port = st.number_input(T(ctx, "settings.field_port"), value=22, min_value=1, max_value=65535, key="new_port")
    with a3:
        new_key = st.text_input(T(ctx, "settings.field_key_path"), value="~/.ssh/id_ed25519", key="new_key")
        new_log = st.text_input(T(ctx, "settings.field_log_path"), value="/var/log/nginx/access.log", key="new_log")
    submitted = st.form_submit_button(T(ctx, "settings.add_server_btn"), use_container_width=True)
    if submitted:
        if not new_name or not new_host:
            st.error(T(ctx, "settings.add_server_validation"))
        else:
            servers.append(
                draft_server_from_form(
                    name=new_name,
                    host=new_host,
                    port=int(new_port),
                    user=new_user,
                    key_path=new_key,
                    key_passphrase_env="SKOPOS_SSH_KEY_PASSPHRASE",
                    access_log_path=new_log,
                    auto_discover_logs=True,
                    auto_discover_docker_logs=False,
                    docker_log_containers="",
                )
            )
            commands_map[new_name] = []
            st.session_state.settings_servers_draft = servers
            st.session_state.settings_ssh_commands = commands_map
            st.success(T(ctx, "settings.add_server_ok"))
            st.rerun()

st.markdown("---")
save_left, save_right = st.columns([1, 2])
with save_left:
    if st.button(T(ctx, "settings.save_config"), type="primary", use_container_width=True):
        try:
            token_env_name = (
                st.session_state.settings_telegram_token_env.strip() or DEFAULT_TELEGRAM_BOT_TOKEN_ENV
            )
            new_token = st.session_state.get("settings_telegram_bot_token_input", "").strip()
            if new_token:
                upsert_env_var(token_env_name, new_token)
                load_app_env()

            new_cfg = config_from_db_settings(cfg, draft_settings_from_session(cfg))
            new_cfg = AppConfig(
                db_path=new_cfg.db_path,
                database_url=new_cfg.database_url,
                geoip_mmdb_path=cfg.geoip_mmdb_path,
                poll_interval_seconds=cfg.poll_interval_seconds,
                batch_lines_per_server=cfg.batch_lines_per_server,
                security_auto_scan=st.session_state.settings_auto_scan,
                security_scan_interval_minutes=int(st.session_state.settings_scan_interval),
                telegram_enabled=st.session_state.settings_telegram_enabled,
                telegram_bot_token_env=token_env_name,
                telegram_chat_id=st.session_state.settings_telegram_chat_id.strip() or None,
                telegram_notify_interval_minutes=int(st.session_state.settings_telegram_notify_interval),
                servers=servers,
            )
            save_config(
                config_path,
                new_cfg,
                ssh_commands=commands_map if custom_ssh_commands_allowed() else {},
            )
            draft = draft_settings_from_session(cfg)
            if draft.mode == "postgres":
                upsert_env_var("SKOPOS_DATABASE_URL", draft.target)
            else:
                remove_env_var("SKOPOS_DATABASE_URL")
            load_app_env()
            st.session_state._settings_loaded_path = None
            st.cache_data.clear()
            st.success(T(ctx, "settings.save_ok"))
        except Exception as e:
            st.error(str(e))
with save_right:
    st.caption(T(ctx, "settings.save_hint"))

with st.expander(T(ctx, "settings.preview_yaml")):
    db_preview = draft_settings_from_session(cfg)
    preview = {
        "db_path": db_preview.db_path,
        **({"database_url": db_preview.target} if db_preview.mode == "postgres" else {}),
        "servers": [
            {
                "name": s.name,
                "source": s.source,
                "ssh": {
                    "host": s.ssh.host,
                    "port": s.ssh.port,
                    "user": s.ssh.user,
                    "key_path": s.ssh.key_path,
                    "key_passphrase_env": s.ssh.key_passphrase_env,
                },
                "nginx": {
                    "access_log_path": s.nginx.access_log_path,
                    "auto_discover_logs": s.nginx.auto_discover_logs,
                    "auto_discover_docker_logs": s.nginx.auto_discover_docker_logs,
                    "docker_log_containers": s.nginx.docker_log_containers,
                },
                **(
                    {
                        "apache": {
                            "enabled": True,
                            "access_log_path": s.apache.access_log_path,
                            "auto_discover_logs": s.apache.auto_discover_logs,
                            "auto_discover_docker_logs": s.apache.auto_discover_docker_logs,
                            **(
                                {"docker_log_containers": s.apache.docker_log_containers}
                                if s.apache.docker_log_containers
                                else {}
                            ),
                        }
                    }
                    if s.apache and s.apache.enabled
                    else {}
                ),
                **({"ssh_commands": commands_map.get(s.name)} if commands_map.get(s.name) else {}),
            }
            for s in servers
        ]
    }
    st.code(json.dumps(preview, ensure_ascii=False, indent=2), language="json")

finalize_page(ctx)
