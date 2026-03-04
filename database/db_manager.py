import sqlite3
import os

# 1. 确定数据库文件的存放路径（就放在 database 文件夹下）
DB_PATH = "database/interview_records.db"

def init_db():
    """初始化数据库并建立数据表"""
    # 连接数据库（如果文件不存在，它会自动帮我们建一个）
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 📝 核心 SQL 语句：创建一张名叫 reports 的表
    # 里面有 4 个格子：序号(id)、用户ID(user_id)、报告内容(report_text)、创建时间(created_at)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            report_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 数据库 [interview_records.db] 与数据表初始化成功！")

def save_report(user_id, report_text):
    """供后厨大厨调用的功能：保存评估报告"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reports (user_id, report_text) VALUES (?, ?)", (user_id, report_text))
    conn.commit()
    conn.close()
    print(f"💾 成功将用户 {user_id} 的报告存入数据库！")

# 只有当我们手动运行这个脚本时，才会执行初始化建表
if __name__ == "__main__":
    init_db()
