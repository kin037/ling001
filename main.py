      - name: 🔍 调试：检查环境变量
        run: |
          echo "正在检查环境变量..."
          # 检查 Key 是否存在
          if [ -z "$FINNHUB_API_KEY" ]; then
            echo "❌ 错误：FINNHUB_API_KEY 为空！"
          else
            echo "✅ 成功：FINNHUB_API_KEY 已找到！"
          fi
          
          # 列出所有变量名（为了安全，不显示值）
          echo "当前所有环境变量名："
          printenv | grep -v "TOKEN\|KEY\|SECRET" || true
        env:
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          PUSHPLUS_TOKEN: ${{ secrets.PUSHPLUS_TOKEN }}
