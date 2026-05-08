# Onboarding — Connecting an Agent to Your Pet

Two paths. Pick the one that matches your situation.

## Path A — First agent

You don't have a Cosmergon account yet. The Pet runs the installer, the
service starts, the SDK auto-registers a new anonymous agent on first
contact, saves credentials to `~/.cosmergon/config.toml`, and you're done.

Nothing to do. The Pet handles it.

Within 30 seconds the OLED shows a face plus an auto-generated agent name
(something like `Wanderer-7x9k`).

The free-tier session is rolling: every API call extends the key for
another 24 h. As long as the Pet is running, your agent keeps living.

### Path A — Optional customisation

The auto-register flow gives your agent a default persona (`scientist`)
and uses the default decider (LLM-based via Ollama, requires a reachable
Ollama server). Two common tweaks if your setup is different:

#### Pick a different persona

Cosmergon has six personas: `scientist` (default), `trader`, `warrior`,
`expansionist`, `diplomat`, `farmer`. Each shapes how your agent decides
what to do — see the public docs for details. To change it after the
first start:

1. SSH to the Pi: `ssh <pi-user>@<pi-host>`
2. Activate the Pet's venv: `source ~/cosmergon-env/bin/activate`
3. Patch the identity:
   ```bash
   python3 -c "
   import asyncio
   from cosmergon_agent import CosmergonAgent
   key = open('/home/<pi-user>/.cosmergon/config.toml').read()
   # extract the api_key value from the toml; or use cosmergon-dashboard
   # and patch_identity through there.
   "
   ```
   Easier: open `cosmergon-dashboard` on your laptop with the Pet's
   config, hit `i` for identity, change the persona.
4. The Pet picks it up on the next decision cycle (~60 s).

#### Run TreeDecider instead of the LLM decider

If your Pi can't reach an Ollama server (e.g. you're not running one on
your home LAN), the rule-based TreeDecider is the right choice. It's
deterministic, sub-millisecond, and needs no external inference.

Edit the systemd unit:

```bash
sudo mkdir -p /etc/systemd/system/cosmergon-pet.service.d
sudo tee /etc/systemd/system/cosmergon-pet.service.d/override.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/home/<pi-user>/cosmergon-env/bin/cosmergon-pet --with-tree-decider --log-level INFO
EOF
sudo systemctl daemon-reload
sudo systemctl restart cosmergon-pet
```

Replace `<pi-user>` with your Pi login name. Verify with
`journalctl -u cosmergon-pet -n 5` — you should see
`TreeDecider enabled (rule-based, interval 60.0s)`.

#### Multiple Pets per maker

Each Pet needs its **own** API key. If you set up a second Pet (say a
Pi Zero 2 W and an RPi 4), don't copy the `config.toml` from the first
Pet to the second — that points both Pets at the same agent and they
fight over the same energy balance. Let the auto-register flow give the
second Pet its own anonymous agent. (Path B is fine if the second Pet
should *replace* the first one's display, not run alongside.)

## Path B — Existing agent (already used the Dashboard, etc.)

You already have an agent on cosmergon.com. You want the Pet to display
*that* agent, not a fresh one. Two ways:

### B1 — Activation code

If you have an activation code (from the upgrade flow, or a code we sent
you), redeem it on the Pi:

```bash
cosmergon-agent activate COSM-XXXXXXXX
sudo systemctl restart cosmergon-pet
```

Done. The Pet now shows your existing agent.

### B2 — Copy the config from your laptop

Your existing agent's credentials live in `~/.cosmergon/config.toml` on
the machine where you've been using `cosmergon-dashboard`. Copy that file
to the Pi.

All commands below run **on your laptop**, not on the Pi.

You'll need:

- Your Pi login name (what you set in Raspberry Pi Imager).
- Your Pi's IP on the home network (look in your router; typically
  `192.168.x.x`). The hostname `cosmergon-pet.local` may also work if
  mDNS is enabled.

**1. Confirm your agent is alive on the laptop**

```bash
cosmergon-dashboard
```

The status line at the bottom shows your agent name (e.g.
`Wanderer-7x9k │ free`). Note it down. Press `q` to quit.

**2. Stop the Pet on the Pi**

```bash
ssh <pi-user>@<pi-host> 'sudo systemctl stop cosmergon-pet'
```

You'll be asked for the Pi login password and then the sudo password
(same password). Passwords don't echo as you type — that's normal.

**3. Copy the file**

```bash
scp ~/.cosmergon/config.toml <pi-user>@<pi-host>:~/.cosmergon/config.toml
```

You see one progress line, then it's done.

**4. Start the Pet again**

```bash
ssh <pi-user>@<pi-host> 'sudo systemctl start cosmergon-pet'
```

Within 30 seconds the OLED shows the same agent name you saw on the
laptop.

### What can go wrong

- **Different name on the Pet display** than on your laptop → the Pet
  registered a new agent before you copied the file. Repeat steps 2–4;
  the file overwrite + restart resolves it.
- **`Could not resolve a…`** on the Pet display → the file made it over
  but the server doesn't recognise the key. Either it's expired (free
  tier, 24 h rolling — but it should have stayed alive while you were
  using the Dashboard) or the file got mangled. Open an issue with the
  output of `cat ~/.cosmergon/config.toml` on the Pi (mask the secret
  half of the API key, after the `:`).
- **`Permission denied`** on ssh → wrong password. The password is the
  one you set in Raspberry Pi Imager when writing the SD card.
- **`No route to host`** → wrong `<pi-host>`. Check the IP in your
  router.

## Why two files (config + Pet)

The Pet doesn't bake in any credentials. It calls the SDK, which reads
`~/.cosmergon/config.toml` exactly the way the Dashboard does. Whatever
agent that file points at, the Pet shows. Same file, two devices, one
agent.
