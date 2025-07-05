# create_re_table.py

"""
最终优化版：解决高频词误选问题
"""

import json
import re
from collections import defaultdict
import jieba
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import math

import logging
logging.getLogger("jieba").setLevel(logging.ERROR)

zh_stop = set()
with open("cn_stopwords.txt", encoding="utf-8") as f:
    for w in f:
        zh_stop.add(w.strip())

def load_docs(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def safe_segment(text):
    """安全分词：处理空字符串并过滤停用词"""
    if not text.strip():
        return []
    return [t for t in jieba.cut(text) if t.strip() and t not in zh_stop]

def segment_fields(docs):
    """处理各字段分词及位置记录，适应空字段和无效关键词"""
    corpus_texts = []
    title_pos_list, abstract_pos_list, author_pos_list, keyword_pos_list = [], [], [], []

    for doc in docs:
        # —— 标题处理（允许空标题）
        title = doc.get("title", "")
        title_tokens = safe_segment(title)
        tp = defaultdict(list)
        for i, t in enumerate(title_tokens):
            tp[t].append(i)
        title_pos_list.append(tp)

        # —— 摘要处理（允许空摘要）
        abstract = doc.get("abstract", "")
        abs_tokens = safe_segment(abstract)
        ap = defaultdict(list)
        for i, t in enumerate(abs_tokens):
            ap[t].append(i)
        abstract_pos_list.append(ap)
        corpus_texts.append(" ".join(abs_tokens))  # 用于TF-IDF计算

        # —— 作者处理（允许空列表，过滤无效作者名）
        auth_map = defaultdict(list)
        for i, name in enumerate(doc.get("author", [])):
            name = name.strip()
            if name and name not in zh_stop:
                auth_map[name].append(i)
        author_pos_list.append(auth_map)

        # —— 关键词处理（过滤"&nbsp"等无效值）
        keyword_map = defaultdict(list)
        for i, keyword in enumerate(doc.get("keyword", [])):
            keyword = keyword.strip()
            if keyword and keyword not in zh_stop and keyword != "&nbsp":
                keyword_map[keyword].append(i)
        keyword_pos_list.append(keyword_map)

    return corpus_texts, title_pos_list, abstract_pos_list, author_pos_list, keyword_pos_list

def sigmoid(x):
    """sigmoid函数，将任意实数映射到(0,1)区间"""
    return 2 / (1 + math.exp(-x)) - 1

def build_inverted_index(title_list, abstract_list, author_list, keyword_list):
    """构建倒排索引，适应空字段，并计算每个词的score"""
    inv = defaultdict(dict)
    total_docs = len(title_list)
    
    # 计算每个词的文档频率(df) - 统计每个词在多少篇文档中出现过
    df = defaultdict(set)
    # 计算每个词的总词频(sum_tf)
    sum_tf = defaultdict(int)
    
    # 新增：计算语料库总词数
    total_corpus_words = 0
    
    for doc_id in range(total_docs):
        # 统计标题中的词
        for term, poses in title_list[doc_id].items():
            df[term].add(doc_id)
            sum_tf[term] += len(poses)
            total_corpus_words += len(poses)  # 累加总词数
        
        # 统计摘要中的词
        for term, poses in abstract_list[doc_id].items():
            df[term].add(doc_id)
            sum_tf[term] += len(poses)
            total_corpus_words += len(poses)  # 累加总词数
    
    # 保存df的原始set形式，用于后续遍历
    df_sets = {term: docs for term, docs in df.items()}
    # 将df从set转换为文档数量
    df = {term: len(docs) for term, docs in df.items()}
    
    # 预计算每个词的score
    term_scores = {}
    
    # 打开文件准备写入
    with open('raw_scores.txt', 'w', encoding='utf-8') as f:
        f.write("词\tTF\tIDF\tRaw_Score\tFinal_Score\n")
        for term in df:
            # 计算IDF：log(1 + 总文档数 / (包含该词的文档数 + 1))
            idf = math.log(1 + total_docs / (df[term] + 1))
            
            # 修正TF计算：对每篇文档分别计算TF后相加
            doc_tf_sum = 0
            for doc_id in df_sets[term]:  # 使用保存的set形式
                # 计算该文档中该词的出现次数
                term_count = 0
                doc_length = 0
                
                # 统计标题中的词频
                if term in title_list[doc_id]:
                    term_count += len(title_list[doc_id][term])
                    doc_length += sum(len(poses) for poses in title_list[doc_id].values())
                
                # 统计摘要中的词频
                if term in abstract_list[doc_id]:
                    term_count += len(abstract_list[doc_id][term])
                    doc_length += sum(len(poses) for poses in abstract_list[doc_id].values())
                
                # 计算该文档中该词的TF值
                if doc_length > 0:  # 避免除零错误
                    doc_tf = math.log(1 + term_count) / math.log(1 + doc_length)
                    doc_tf_sum += doc_tf
            
            tf = math.log(1 + doc_tf_sum)
            
            # 计算TF-IDF
            raw_score = math.log(1 + math.sqrt(tf) * idf * idf * idf)
            
            # 使用sigmoid函数将分数映射到(0,1)区间
            # 使用缩放因子3来调整sigmoid曲线的陡峭程度
            final_score = sigmoid(raw_score / 3)
            term_scores[term] = final_score
            
            # 写入文件
            f.write(f"{term}\t{tf:.6f}\t{idf:.6f}\t{raw_score:.6f}\t{final_score:.6f}\n")
    
    # 构建倒排索引
    for doc_id in range(total_docs):
        # 处理标题
        for term, poses in title_list[doc_id].items():
            inv[term].setdefault(doc_id, {
                "title_positions": [], 
                "abstract_positions": [],
                "author_positions": [],
                "keyword_positions": [],
                "score": term_scores[term]  # 使用预计算的score
            })["title_positions"] = poses
            
        # 处理摘要
        for term, poses in abstract_list[doc_id].items():
            inv[term].setdefault(doc_id, {
                "title_positions": [], 
                "abstract_positions": [],
                "author_positions": [],
                "keyword_positions": [],
                "score": term_scores[term]  # 使用预计算的score
            })["abstract_positions"] = poses
                
        # 处理作者 - score固定为1
        for term, poses in author_list[doc_id].items():
            inv[term].setdefault(doc_id, {
                "title_positions": [], 
                "abstract_positions": [],
                "author_positions": [],
                "keyword_positions": [],
                "score": 1.0  # 作者score固定为1
            })["author_positions"] = poses
            
        # 处理关键词 - score固定为1
        for term, poses in keyword_list[doc_id].items():
            inv[term].setdefault(doc_id, {
                "title_positions": [], 
                "abstract_positions": [],
                "author_positions": [],
                "keyword_positions": [],
                "score": 1.0  # 关键词score固定为1
            })["keyword_positions"] = poses
            
    return inv

def save_index(inv, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(inv, f, ensure_ascii=False, indent=2)

def main():
    json_in, json_out = 'papers.json', 're_idx.json'
    print("加载文档...")
    docs = load_docs(json_in)
    
    print("处理字段分词...")
    corpus, tpos, apos, upos, kpos = segment_fields(docs)
    
    print("构建倒排索引...")
    inv = build_inverted_index(tpos, apos, upos, kpos)
    
    print("保存索引文件...")
    save_index(inv, json_out)
    print("完成！")

if __name__ == "__main__":
    main()