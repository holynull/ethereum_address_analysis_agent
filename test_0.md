```python
@tool
def get_balances_of_address(address: str):
    """
    Obtains the balance of all tokens for a specified address and provides a distribution chart in USD. Input should be a complete Ethereum address.
    """

    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=3)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_token_balance_of_address",
        query_id=3916915,
        params=[
            QueryParameter.text_type(name="address", value=address),
        ],
    )
    results_df = dune.run_query_dataframe(query=query)
    if not results_df.empty:
        # 从数据中提取标签和余额
        labels = results_df["token_symbol"].apply(lambda x: x if x else "NaN").tolist()
        sizes = (
            results_df["balance_usd"]
            .apply(lambda item: float(item) if item != "<nil>" else 0)
            .tolist()
        )
        if sum(sizes) > 0:

            # 创建 explode 参数，增加一些偏移量以增强立体效果
            explode = [
                0.1 if size > 0.05 * sum(sizes) else 0 for size in sizes
            ]  # 只有当占比大于5%时才抬起

            # 创建饼状图
            plt.figure(figsize=(12, 8), dpi=80)
            wedges, texts, autotexts = plt.pie(
                sizes,
                labels=[
                    label if size > 0.05 * sum(sizes) else " "
                    for label, size in zip(labels, sizes)
                ],  # 只显示大于5%的标签
                autopct=lambda p: f"{p:.1f}%" if p > 5 else "",  # 只显示大于5%的百分比
                startangle=140,
                explode=explode,
                shadow=True,
                textprops={"fontsize": 12},  # 设置字体大小
                pctdistance=0.85,  # 设置百分比文本的位置
            )

            # 删除连接线逻辑，保持饼图简单

            # 设置图例，增加宽度和多行显示
            plt.legend(
                wedges,
                labels,
                title="Tokens",
                loc="center left",
                bbox_to_anchor=(1, 0, 0.5, 1),
                ncol=2,
                fontsize=10,  # 设置图例的列数为2
            )

            plt.title("Token Balance Distribution in USD")
            plt.axis("equal")  # 使饼状图是一个正圆

            # 设置背景透明
            plt.gca().patch.set_alpha(0.0)  # Set background to transparent

            random_filename = f"token_balance_distribution_{uuid.uuid4()}.png"
            plt.savefig(random_filename, format="png")
            plt.close()
            
            # 上传文件到 S3 存储桶的 charts 文件夹
            s3_client.upload_file(random_filename, 'musse.ai', f'charts/{random_filename}')
            img_str = (
                f"Description of Image: Token Balance Distribution in USD"
                + "\n"
                + f"Image Url:https://musse.ai/charts/{random_filename}"
            )
            r_arr = results_df.apply(
                lambda row: f"Token: {row['token_symbol']}\nContract address: {row['token_address']}\n"
                + f"Balance: {row['balance']} (USD: {row['balance_usd']} Price:${row['price_usd']})",
                axis=1,
            ).tolist()
            result = f"## Balances of address {address}:\n" + "\n".join(r_arr)
            return result + "\n\n" + img_str
        else:
            r_arr = results_df.apply(
                lambda row: f"Token: {row['token_symbol']}\nContract address: {row['token_address']}\n"
                + f"Balance: {row['balance']} (USD: {row['balance_usd']} Price:${row['price_usd']})",
                axis=1,
            ).tolist()
            result = f"## Balances of address {address}:\n" + "\n".join(r_arr)
            return result
    else:
        return "No Balances Found."
```

如何把生成的图片文件上传到musse.ai这个桶的charts文件中，然后在本地删除掉这个文件。
