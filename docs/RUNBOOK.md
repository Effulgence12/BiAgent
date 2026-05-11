# 运行与验收手册

## 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. 准备数据

项目启动时会优先使用 `data/raw/` 中已有 CSV；如果缺失，会尝试从公开 GitHub 镜像下载 Olist CSV；如果下载失败，会生成结构接近真实 Olist 的模拟 CSV。

也可以手动执行：

```bash
python cli.py --bootstrap "2017年各月GMV趋势？"
```

## 3. 启动 Web

```bash
uvicorn app:app --reload
```

访问 <http://127.0.0.1:8000>。

## 4. 建议验收问题

1. `2017年各月GMV趋势？`
2. `哪些州销售额最高？`
3. `哪些州配送延迟严重，原因是什么？`
4. `品类销售额Top10是什么？`
5. `支付方式和分期数分布如何？`
6. `卖家中哪些评分最低？`
7. `重量和运费是否相关？`
8. `预测未来6期GMV。`
9. `给出平台整体运营优化建议。`
10. `分析东北部降低延迟率的策略。`
