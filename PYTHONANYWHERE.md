# PythonAnywhere Free Setup

This app now exposes a Flask WSGI application for PythonAnywhere. Its free tier currently has one web app, 100 CPU seconds, 512 MiB of storage, and a one-month web-app expiry. It is suitable for a small trial, not guaranteed permanent hosting.

## Prepare the free account

1. Create a free account at [PythonAnywhere](https://www.pythonanywhere.com/pricing/).
2. Open a Bash console and run:

```sh
git clone https://github.com/homidark/web.git
cd web
python3.13 -m venv ~/.virtualenvs/homi
~/.virtualenvs/homi/bin/pip install -r requirements.txt
```

3. Open the **Web** tab and add a web app. Choose **Manual configuration** and the same Python version, then set the virtualenv to `/home/YOUR_USERNAME/.virtualenvs/homi`.
4. Open the WSGI configuration file linked from the Web tab. Set the project path and import the app:

```python
import os
import sys

path = "/home/YOUR_USERNAME/web"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["OWNER_USERNAME"] = "homidark"
os.environ["OWNER_PASSWORD"] = "PUT_A_UNIQUE_SECRET_HERE"

from wsgi import application
```

Replace both `YOUR_USERNAME` values with your PythonAnywhere username. Replace the password placeholder with a unique secret directly in PythonAnywhere. Never put the real password in GitHub or send it in chat.

5. Save the WSGI file, return to the Web tab, and click **Reload**. Your site will be at `https://YOUR_USERNAME.pythonanywhere.com`.

The account database and owner-edited site content are written under `/home/YOUR_USERNAME/web`, which is within your PythonAnywhere home directory. The free account's CPU/storage limits still apply; a service restart clears in-memory sessions. Keep the free-plan expiry in mind.