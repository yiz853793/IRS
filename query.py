# query.py
# -*- coding: utf-8 -*-

import json
import jieba
import pyreadline   # 历史命令和箭头上下切换
from collections import defaultdict
import datetime

# ----------------- 配置区 -----------------
DATA_PATH = "papers.json"
INDEX_PATH = "re_idx.json"
LOG_PATH = "feedback.log"

import logging
logging.getLogger("jieba").setLevel(logging.ERROR)

# 加载停用词表
zh_stop = set()
with open("cn_stopwords.txt", encoding="utf-8") as f:
    for w in f:
        zh_stop.add(w.strip())

TITLE_WEIGHT    = 5.0
AUTHOR_WEIGHT   = 50.0
KEYWORD_WEIGHT  = 10.0
ABSTRACT_WEIGHT = 1.0

SNIPPET_WINDOW = 20
TOPK = 10
# ------------------------------------------

def load_data():
    with open(DATA_PATH, encoding='utf-8') as f:
        docs = json.load(f)
    with open(INDEX_PATH, encoding='utf-8') as f:
        inv = json.load(f)
        inv = {term: {int(d): fields for d, fields in postings.items()}
               for term, postings in inv.items()}
    return docs, inv

def highlight_title(title, hit_list):
    title_terms = [term for (field, term) in hit_list if field == 'title']
    unique_terms = list(set(title_terms))
    unique_terms.sort(key=lambda x: len(x), reverse=True)
    tokens = list(jieba.cut(title))
    highlighted = [False] * len(tokens)
    for term in unique_terms:
        for i, token in enumerate(tokens):
            if token == term and not highlighted[i]:
                tokens[i] = f'【{token}】'
                highlighted[i] = True
    return ''.join(tokens)

def highlight_abstract(abstract, hit_list):
    abstract_terms = [term for (field, term) in hit_list if field == 'abstract']
    unique_terms = list(set(abstract_terms))
    unique_terms.sort(key=lambda x: len(x), reverse=True)
    tokens = list(jieba.cut(abstract))
    highlighted = [False] * len(tokens)
    for term in unique_terms:
        for i, token in enumerate(tokens):
            if token == term and not highlighted[i]:
                tokens[i] = f'【{token}】'
                highlighted[i] = True
    return ''.join(tokens)

def highlight_authors(authors, hit_list):
    hit_terms = {term for (field, term) in hit_list if field == 'author'}
    return [f'【{a}】' if a in hit_terms else a for a in authors]

def highlight_keywords(keywords, hit_list):
    hit_terms = {term for (field, term) in hit_list if field == 'keyword'}
    return [f'【{kw}】' if kw in hit_terms else kw for kw in keywords]

def search(docs, inv, query):
    tokens = [t for t in jieba.cut(query) if t.strip() and t not in zh_stop]
    author_terms = [name for doc in docs for name in doc.get("author", []) if name in query]
    keyword_terms = [kw for doc in docs for kw in doc.get("keyword", []) if kw in query]

    scores = defaultdict(float)
    hits  = defaultdict(list)

    for term in tokens:
        posting = inv.get(term, {})
        for doc_id, fields in posting.items():
            if fields["title_positions"]:
                scores[doc_id] += TITLE_WEIGHT * fields["score"]
                hits[doc_id].append(("title", term))
            if fields["abstract_positions"]:
                scores[doc_id] += ABSTRACT_WEIGHT * fields["score"]
                hits[doc_id].append(("abstract", term))

    for name in set(author_terms):
        posting = inv.get(name, {})
        for doc_id, fields in posting.items():
            if fields["author_positions"]:
                scores[doc_id] += AUTHOR_WEIGHT * fields["score"]
                hits[doc_id].append(("author", name))

    for kw in set(keyword_terms):
        posting = inv.get(kw, {})
        for doc_id, fields in posting.items():
            if fields["keyword_positions"]:
                scores[doc_id] += KEYWORD_WEIGHT * fields["score"]
                hits[doc_id].append(("keyword", kw))

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:TOPK]
    results = []
    for doc_id, score in ranked:
        doc = docs[doc_id]
        hit_list = hits.get(doc_id, [])
        results.append({
            "score": score,
            "title": highlight_title(doc.get("title", ""), hit_list),
            "snippet": highlight_abstract(doc.get("abstract", ""), hit_list),
            "url": doc.get("url", ""),
            "date": doc.get("date", ""),
            "author": highlight_authors(doc.get("author", []), hit_list),
            "keyword": highlight_keywords(doc.get("keyword", []), hit_list)
        })
    return results

def get_feedback(last_query, last_results):
    """获取多行评价内容"""
    print("\n请对本次搜索进行评价（连续两次Enter结束）：")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    feedback = "\n".join(lines)
    
    # 构建日志内容
    log_content = []
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content.append(f"[评价时间] {timestamp}")
    log_content.append(f"搜索词: {last_query}")
    
    if last_results:
        log_content.append(f"\nTop{len(last_results)} 搜索结果：")
        for idx, r in enumerate(last_results, 1):
            log_content.append(f"{idx}. 相关度: {r['score']:.2f}\n")
            log_content.append(f"   标题: {r['title']}\n")
            log_content.append(f"   作者: {' '.join(r['author'])}\n")
            log_content.append(f"   摘要: {r['snippet']}\n")
            log_content.append(f"   关键词: {' '.join(r['keyword'])}\n")
            log_content.append(f"   URL: {r['url']}\n")
            log_content.append(f"   日期: {r['date']}\n\n")
    else:
        log_content.append("未找到相关内容。")
    
    log_content.append(f"用户评价：\n{feedback}")
    log_content.append("-" * 50)
    
    return "\n".join(log_content)

def main():
    print("加载数据…")
    docs, inv = load_data()
    print("查询程序启动，输入 exit 退出，输入 rate 进行评价")

    last_query = None
    last_results = None

    while True:
        user_input = input("\n请输入查询/命令：").strip()
        if user_input.lower() == "exit":
            print("拜拜！")
            break
        elif user_input.lower() == "rate":
            if last_query is None:
                print("尚未进行过搜索")
                continue
                
            feedback_log = get_feedback(last_query, last_results)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(feedback_log + "\n")
            print("感谢评价！")
        else:
            # 执行搜索并记录状态
            last_query = user_input
            last_results = search(docs, inv, user_input)
            
            if not last_results:
                print("未找到相关内容。")
            else:
                print(f"\nTop{len(last_results)} 搜索结果：")
                for idx, r in enumerate(last_results, 1):
                    print(f"{idx}. 相关度: {r['score']:.2f}")
                    print(f"   标题: {r['title']}")
                    print(f"   作者: {' '.join(r['author'])}")
                    print(f"   摘要: {r['snippet']}")
                    print(f"   关键词: {' '.join(r['keyword'])}")
                    print(f"   URL: {r['url']}")
                    print(f"   日期: {r['date']}\n")

if __name__ == "__main__":
    main()