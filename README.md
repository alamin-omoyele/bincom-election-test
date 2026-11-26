# Bincom Election Test

A small web app that shows election results from a MySQL database.
It answers three questions:

1. **Q1** — View the result of one polling unit.

2. **Q2** — Add up all polling unit results inside one LGA and compare with the announced LGA result.

3. **Q3** — Add a new polling unit and enter scores for every party.

No frameworks. Just Python + MySQL + a browser.

## What you need before starting

Install these once, then forget about them:

1. **Python 3.9 or newer** — https://www.python.org/downloads/

   * On Windows, tick **"Add Python to PATH"** during install.

2. **MySQL** — https://dev.mysql.com/downloads/installer/

   * During install, remember the **root password** you set. You'll need it.

3. **Git** (optional, only if you're cloning) — https://git-scm.com/downloads

To check everything is installed, open a terminal (Command Prompt / PowerShell / Terminal) and run:

```
python --version
mysql --version

```

You should see version numbers. If you get "command not found", reinstall and make sure the box that adds it to PATH is ticked.

## Setup — step by step

### Step 1 — Get the project

If you downloaded the ZIP, unzip it. If you're cloning:

```
git clone https://github.com/YOUR_USERNAME/bincom-election-test.git
cd bincom-election-test

```

You should now be inside a folder that contains `app.py` and `bincom_test.sql`.

### Step 2 — Import the database

The file `bincom_test.sql` creates the database and fills it with data. You only do this once.

**Open a terminal in the project folder** and run:

```
mysql -u root -p < bincom_test.sql

```

It will ask for your MySQL root password — type it (nothing shows on screen, that's normal) and press Enter.

> **Windows note:** if `mysql` isn't recognised, use the full path, usually:
>
> ```
> "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p < bincom_test.sql
> 
> ```

To confirm it worked, log into MySQL:

```
mysql -u root -p

```

Then inside MySQL:

```
SHOW DATABASES;

```

You should see `bincomphptest` in the list. Type `exit` to leave.

### Step 3 — Create a database user (recommended)

The app needs a user that can access `bincomphptest`. You can use `root`, but it's cleaner to make a dedicated user.

Still inside MySQL (`mysql -u root -p`), run:

```
CREATE USER 'bincom'@'localhost' IDENTIFIED BY 'bincom123';
GRANT ALL PRIVILEGES ON bincomphptest.* TO 'bincom'@'localhost';
FLUSH PRIVILEGES;
exit;

```

> If you'd rather use `root`, skip this step and just put `root` + your root password in the `.env` file later.

### Step 4 — Install the Python dependencies

In the project folder, run:

```
# Create a virtual environment (a private Python sandbox for this project)
python -m venv venv

```

Activate it:

* **Windows (PowerShell):**

  ```
  venv\Scripts\Activate.ps1
  
  ```

* **Windows (Command Prompt):**

  ```
  venv\Scripts\activate.bat
  
  ```

* **macOS / Linux:**

  ```
  source venv/bin/activate
  
  ```

You should see `(venv)` at the start of your terminal prompt.

Now install the packages:

```
pip install -r requirements.txt

```

### Step 5 — Create your `.env` file

The app reads your database details from a file called `.env`.

Copy the example file:

* **Windows:**

  ```
  copy .env.example .env
  
  ```

* **macOS / Linux:**

  ```
  cp .env.example .env
  
  ```

Open `.env` in any text editor (Notepad, VS Code, etc.) and fill in your real values:

```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=bincom
DB_PASSWORD=bincom123
DB_NAME=bincomphptest
PORT=8000

```

> If you skipped Step 3 and are using `root`, change `DB_USER` to `root` and `DB_PASSWORD` to your root password.

Save and close the file.

### Step 6 — Run the app

Make sure your virtual environment is still active (you see `(venv)` in the prompt). Then:

```
python app.py

```

You should see:

```
Server running on http://localhost:8000

```

Open **http://localhost:8000** in your browser. 🎉

To stop the server, press **Ctrl + C** in the terminal.

## Using the app

* **Q1 — Polling Unit Result:** pick an LGA → a Ward → a Polling Unit. The party scores for that unit appear.

* **Q2 — LGA Summed Results:** pick an LGA. You get the sum of every polling unit in it, plus the officially announced LGA result next to it.

* **Q3 — Add New Polling Unit:** fill in the details, enter a score for every party, click save. The new unit is stored in the database.

## Troubleshooting

| Problem | Fix | 
| ----- | ----- | 
| `python: command not found` | Reinstall Python and tick **"Add Python to PATH"**. On macOS/Linux try `python3` instead. | 
| `pip: command not found` | Make sure the virtual environment is activated (you see `(venv)` in the prompt). | 
| `ModuleNotFoundError: No module named 'mysql'` | Run `pip install -r requirements.txt` again while `(venv)` is active. | 
| `Access denied for user 'bincom'@'localhost'` | Your `.env` username or password is wrong. Re-check Step 3 and Step 5. | 
| `Unknown database 'bincomphptest'` | The SQL import failed. Re-run Step 2. | 
| `Can't connect to MySQL server` | MySQL isn't running. Open MySQL Workbench, or on Windows run `net start MySQL80`, on macOS `brew services start mysql`. | 
| `Missing required environment variable: DB_HOST` | You didn't create `.env`, or it's in the wrong folder. It must sit next to `app.py`. | 
| `Address already in use` on port 8000 | Another app is using that port. Change `PORT=8001` in `.env` and restart. | 
| Browser shows a blank page | Check the terminal — the error is printed there. Usually a DB connection problem. | 

## Project files

```
bincom-election-test/
├── app.py               # the whole app
├── bincom_test.sql      # database dump — import once (Step 2)
├── requirements.txt     # Python packages
├── .env.example         # template for your DB settings
├── .env                 # YOUR real settings (never commit this)
├── .gitignore
└── README.md

```

## Notes

* The app is locked to **Delta State** (`state_id = 25`) to match the test brief.

* No login or authentication — it's a local test tool, not production software.

* The bundled `bincom_test.sql` includes the demo data, so you should see results immediately after importing it.