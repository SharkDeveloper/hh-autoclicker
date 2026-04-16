# HH Auto Apply

An automated tool for applying to jobs on the Russian recruitment platform HeadHunter (hh.ru).

## Overview

This tool automates the job search and application process by:
- Searching for vacancies based on user-defined keywords and filters
- Handling authentication on hh.ru
- Applying to vacancies with personalized cover letters
- Simulating human behavior (random delays, custom User-Agents) to avoid bot detection
- Logging activities and tracking applied vacancies to prevent duplicates

## Tech Stack

- **Language**: Python 3.12
- **Browser Automation**: Selenium + WebDriver Manager
- **HTML Parsing**: BeautifulSoup4, lxml
- **HTTP**: requests
- **Other**: fake-useragent, python-dotenv, python-dateutil

## Project Structure

```
hh_auto_apply/          # Main modular application
  main.py               # Entry point
  src/
    core/               # Application logic, config, session management
    modules/            # Functional modules (auth, search, apply, resume, monitor)
    ui/                 # CLI interface
    utils/              # Helper functions (browser, data, logging)
  config/               # JSON configuration files
  data/                 # Cover letter templates, manual vacancy lists
  tests/                # Unit tests
hh_auto_apply.py        # Legacy monolithic script version
requirements.txt        # Root dependencies
config.example.json     # Example configuration template
```

## Configuration

Copy `config.example.json` to `hh_auto_apply/config/default.json` and fill in:
- `hh_credentials`: Your hh.ru email and password
- `search_filters`: Resume ID, salary, area, experience level
- `application_settings`: Cover letter, delay, max applications per day
- `browser_settings`: Headless mode, timeouts

## Running

The workflow runs `python3 main.py --help` to show available CLI options.

To actually run job applications, configure `hh_auto_apply/config/default.json` and use:

```bash
cd hh_auto_apply && python3 main.py --mode auto --keywords "Python developer" --area "Москва"
```

## Workflow

- **Start application**: Console workflow running `cd hh_auto_apply && python3 main.py --help`
