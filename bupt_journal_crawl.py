# bupt_journal_crawl.py

import requests
from lxml import etree
from urllib.parse import urljoin
import re
import json

journal_url_set = set()  # 使用set来存储唯一的URL

for year in range(1960,2026):
    url = f'https://journal.bupt.edu.cn/CN/article/showTenYearVolumnDetail.do?nian={year}'
    # print(url)
    while True:
        try:
            response = requests.get(url=url, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200:  # 确保请求成功
                # print(f'成功下载网页{url}')
                break
            else:
                print(f"下载网页失败，状态码：{response.status_code}")
        except Exception as e:
            print(f"下载网页时发生错误：{e}")
            continue
    # print(response.content)
    html = etree.HTML(response.content)

    # journal_lists = html.xpath('//div[@class="item-content"]/table/tr')[-1]
    journal_urls = html.xpath('//a[@class="J_WenZhang"]/@href')
    # print(len(journal_urls))
    # 将新的URL添加到set中，set会自动去重
    for journal_url in journal_urls:
        journal_url = urljoin(url, journal_url)
        journal_url_set.add(journal_url)

def process_authors(raw_authors):
    # 统一处理中英文逗号，分割作者
    authors = re.split(r'[，,;；]\s*', raw_authors)
    
    cleaned_authors = []
    for author in authors:
        if len(author) > 5:
            t = author.split(' ')
            for i in t:
                clean_author = re.sub(r'[^\u4e00-\u9fa5]', '', i)
                if clean_author:  # 过滤空字符串
                    cleaned_authors.append(clean_author)
        else:
            # 去除所有非中文字符和空格
            clean_author = re.sub(r'[^\u4e00-\u9fa5]', '', author)
            if clean_author:  # 过滤空字符串
                cleaned_authors.append(clean_author)
    
    # 合并单字与后一个元素
    merged_authors = []
    i = 0
    while i < len(cleaned_authors):
        current = cleaned_authors[i]
        if len(current) == 1 and i < len(cleaned_authors) - 1:
            # 合并当前单字和下一个元素
            merged = current + cleaned_authors[i + 1]
            merged_authors.append(merged)
            i += 2  # 跳过下一个元素
        else:
            merged_authors.append(current)
            i += 1
    return merged_authors

class paper:
    def __init__(self, title, author, abstract, url, date):
        self.title = title
        self.author = author
        self.abstract = abstract
        self.url = url
        self.date = date
    
    def get_keyword(self, keyword):
        self.keyword = keyword

    def to_dict(self):
        return {
            "title": self.title,
            "author": self.author,
            "date": self.date,
            "abstract": self.abstract,
            "keyword": self.keyword,
            "url": self.url            
        }

origin_paper_list : list[paper] = []
for journal_url in journal_url_set:
    while True:
        try:
            response = requests.get(url=journal_url, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200:  # 确保请求成功
                # print(f'成功下载网页{journal_url}')
                break
            else:
                print(f"下载网页失败，状态码：{response.status_code}")
        except Exception as e:
            print(f"下载网页时发生错误：{e}")
            continue
    html = etree.HTML(response.content.decode('utf-8', errors='ignore').replace('<M', '< M'))
    date = html.xpath('//span[@class="published"]/text()')[0].strip()[5:]
    # print(date)
    paper_blocks = html.xpath('//div[@class="current-content"]/ul[@class="lunwen"]')
    a = 0
    for paper_block in paper_blocks:
        a += 1
        if journal_url == 'https://journal.bupt.edu.cn/CN/volumn/volumn_1358.shtml' and a == 2:
            true_paper_block = paper_block.xpath('.//*[@class="biaoti"]')[0]
            title = true_paper_block.xpath('./a/text()')[0]
            url = true_paper_block.xpath('./a/@href')[0].strip()
            # print(url)
            authors = paper_block.xpath('.//*[@class="zuozhe"]/text()')[0].strip().replace('\xa0', ' ').replace('\ue003', '').encode('gbk', errors='ignore').decode('gbk')
            author_list = process_authors(authors)
            # print(','.join(author_list))
            abstract = paper_block.xpath('.//*[@class="zuozhe white_content"]/div/text()')[0]
            origin_paper_list.append(paper(title, author_list, abstract, url, date))
        else:
            title_elements = paper_block.xpath('.//*[@class="biaoti"]//text()')
            title = ''.join(title_elements).strip().replace('\xa0', ' ').replace('\ue003', '').encode('gbk', errors='ignore').decode('gbk')
            title = re.sub(r'[\s\n\t\r]+', '', title)
            authors = paper_block.xpath('.//*[@class="zuozhe"]/text()')[0].strip().replace('\xa0', ' ').replace('\ue003', '').encode('gbk', errors='ignore').decode('gbk')
            if len(authors) == 0:
                authors = paper_block.xpath('.//*[@class="zuozhe"]/div/text()')
                if len(authors):
                    authors = authors[0].strip().replace('\xa0', ' ').replace('\ue003', '').encode('gbk', errors='ignore').decode('gbk')
                else: authors = ''
            author_list = process_authors(authors)
            abstract = paper_block.xpath('.//*[@class="zuozhe white_content"]//text()')
            abstract = ''.join(abstract).strip().replace('\xa0', ' ').replace('\ue003', '').encode('gbk', errors='ignore').decode('gbk')
            abstract = re.sub(r'[\n\r\t]+', '', abstract)

            url = paper_block.xpath('.//*[@class="biaoti"]//a/@href')[0].strip()
            origin_paper_list.append(paper(title, author_list, abstract, url, date))

paper_list : list[paper] = []
for Paper in origin_paper_list:
    while True:
        try:
            response = requests.get(url=Paper.url, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200:  # 确保请求成功
                # print(f'成功下载网页{Paper.url}')
                # print(f'论文题目为{Paper.title}')
                break
            else:
                print(f"下载网页失败，状态码：{response.status_code}")
        except Exception as e:
            print(f"下载网页时发生错误：{e}")
            continue
    html = etree.HTML(response.content)
    keywords = html.xpath('//form[@name="refForm"]/p[1]/a/text()') if html is not None else []
    keywords = [re.sub(r'[\n\s\t\r,，；;(&nbsp)]+','',keyword.strip()) for keyword in keywords]
    # print(keywords)
    Paper.get_keyword(keywords)
    paper_list.append(Paper)

paper_dict_list = [paper.to_dict() for paper in paper_list]

with open("papers.json", "w", encoding="utf-8") as f:
    json.dump(paper_dict_list, f, ensure_ascii=False, indent=4)

print(f"已存储 {len(paper_dict_list)} 篇论文到 papers.json")

