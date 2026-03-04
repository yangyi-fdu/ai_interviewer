import streamlit as st
import sqlite3
import pandas as pd

# 1. 设置网页的标签页标题和页面布局
st.set_page_config(page_title="AI 面试官管理后台", page_icon="👔", layout="wide")

# 2. 页面主标题
st.title("👔 赛博面试官 - 候选人评估报告管理中心")
st.markdown("---") # 画一条分割线

# 3. 连接数据库并抓取数据的函数
def load_data():
    # 连上我们上一步建好的永久记忆硬盘
    conn = sqlite3.connect("database/interview_records.db")
    # 用 Pandas 直接把数据库里的表捞出来，顺便把英文列名翻译成中文
    query = """
    SELECT 
        id as '面试序号', 
        user_id as '用户ID', 
        created_at as '交卷时间', 
        report_text as '详细报告' 
    FROM reports 
    ORDER BY created_at DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# 获取数据
df = load_data()

# 4. 在网页上展示数据
if df.empty:
    st.warning("📭 数据库里空空如也，快去 Discord 里让机器人面试几个候选人吧！")
else:
    # 顶部数据概览
    st.success(f"📈 数据库连接成功！目前已永久收录 **{len(df)}** 份面试评估报告。")
    
    # 侧边栏放一个刷新按钮
    if st.sidebar.button("🔄 刷新最新数据"):
        st.rerun()

    # 核心组件 1：全景数据表格 (隐藏详细报告那一长串文字，保持表格清爽)
    st.markdown("### 📊 候选人总览")
    st.dataframe(df[['面试序号', '用户ID', '交卷时间']], use_container_width=True)
    
    st.markdown("---")
    
    # 核心组件 2：单人详细报告查看器
    st.markdown("### 🔍 深度报告查阅")
    # 做一个下拉菜单，让你可以选择看几号候选人
    selected_id = st.selectbox("请选择你要查阅的【面试序号】查看完整 AI 评价：", df['面试序号'].tolist())
    
    if selected_id:
        # 提取选中那一行对应的报告文本
        report_content = df[df['面试序号'] == selected_id]['详细报告'].values[0]
        st.info(f"正在展示 序号 {selected_id} 的深度评估：")
        # 用 markdown 完美渲染 AI 写的报告（加粗、列表全都有）
        st.markdown(report_content)
