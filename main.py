name: Generate Report

on:
  schedule:
    - cron: '0 23 * * *' # 每天北京时间早上7点运行 (UTC 23:00)
  workflow_dispatch:     # 允许手动点击运行

jobs:
  generate:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      # --- 关键修复步骤：在这里显式传递环境变量 ---
      - name: Run python main.py
        run: python main.py
        env:
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          PUSHPLUS_TOKEN: ${{ secrets.PUSHPLUS_TOKEN }}
     
