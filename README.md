# NexDay

NexDay is a personal planner that helps you organize your weekly tasks with a single click. 
Its goal is to provide a clear overview of your schedule and help you distribute your activities 
throughout the week.

## Installation Guide

### 1. Clone the project

```bash
git clone https://github.com/Tezay/NexDay.git
cd NexDay
```
### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

#### For Windows
```bash
.venv\Scripts\activate
```

#### For Linux/MacOS
```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Start the Flask server

```bash
flask run
```
Now open your browser and go to http://127.0.0.1:5000 to use NexDay locally.

## Quick Overview

You can add your activities, check availabilities, and automatically generate
an iCal calendar to integrate your schedule with other services.