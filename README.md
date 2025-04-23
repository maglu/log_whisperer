# Log Whisperer

An AI-powered log file analyzer that helps identify and summarize issues in log files.

## Features

- Automatic log file discovery and inventory
- AI-powered log analysis
- Structured issue reporting
- Color-coded output
- Cache support for faster subsequent runs

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/log_whisperer.git
cd log_whisperer
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your Google API key:
```bash
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

## Usage

1. Initialize log inventory:
```bash
python whisp.py init
```

2. Analyze a specific log file:
```bash
python whisp.py analyze -f /path/to/logfile.log
```

Enable debug mode with `-d` flag:
```bash
python whisp.py analyze -f /path/to/logfile.log -d
```

## Requirements

- Python 3.10+
- Google API key for Gemini AI
- Read access to log files

## License

MIT