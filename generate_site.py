import os
from jinja2 import Environment, FileSystemLoader
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from collections import defaultdict
import gzip
import config

# 读取所有分割的 CSV 文件
data_dir = 'data/split_files'
files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith('.csv')]

# 合并所有小文件
data = pd.concat((pd.read_csv(f, encoding='latin-1') for f in files), ignore_index=True)

# 提取推文内容和用户名（假设第六列为推文内容，第五列为用户名）
texts = data.iloc[:, 5].tolist()
usernames = data.iloc[:, 4].tolist()

# 向量化文本数据
vectorizer = CountVectorizer(max_df=0.95, min_df=2, stop_words='english')
X = vectorizer.fit_transform(texts)

# 设置主题数量
n_topics = 200

# 进行LDA主题建模
lda = LatentDirichletAllocation(n_components=n_topics, random_state=42)
lda.fit(X)

# 获取主题关键词
feature_names = vectorizer.get_feature_names_out()
topic_keywords = []
for idx, topic in enumerate(lda.components_):
    topic_keywords.append([feature_names[i] for i in topic.argsort()[-10:]])

# 获取每条推文的主题
doc_topic = lda.transform(X)
doc_topic_labels = doc_topic.argmax(axis=1)

# 根据主题组织推文
grouped_tweets = defaultdict(list)
grouped_usernames = defaultdict(list)
for idx, label in enumerate(doc_topic_labels):
    grouped_tweets[label].append(texts[idx])
    grouped_usernames[label].append(usernames[idx])

# 创建Jinja2模板环境
env = Environment(loader=FileSystemLoader('templates'))
env.globals.update(zip=zip)

# 创建生成目录
if not os.path.exists('web/content'):
    os.makedirs('web/content')

# 每页推文数量
tweets_per_page = 10

# 生成主题页面
content_template = env.get_template('content.html')
sub_sitemap_template = env.get_template('sub_sitemap.xml')

for topic_id, tweets in grouped_tweets.items():
    keywords = topic_keywords[topic_id]
    title = ' '.join(keywords[:3])  # 使用前三个关键词作为标题
    usernames_list = grouped_usernames[topic_id]
    total_pages = (len(tweets) // tweets_per_page) + 1

    # 生成子站点地图
    sub_sitemap_entries = [
        {"loc": f"{config.DOMAIN}/content/topic_{topic_id}_page{page + 1}.html"}
        for page in range(total_pages)
    ]
    sub_sitemap_content = sub_sitemap_template.render(entries=sub_sitemap_entries)
    sub_sitemap_path = f'web/content/topic_{topic_id}_sitemap.xml'
    with open(sub_sitemap_path, 'w') as f:
        f.write(sub_sitemap_content)

    for page in range(total_pages):
        start_idx = page * tweets_per_page
        end_idx = start_idx + tweets_per_page
        page_tweets = tweets[start_idx:end_idx]
        page_usernames = usernames_list[start_idx:end_idx]
        url = f'content/topic_{topic_id}_page{page + 1}.html'
        html_content = content_template.render(
            title=title,
            tweets=page_tweets,
            usernames=page_usernames,
            topic_id=topic_id,
            page=page + 1,
            total_pages=total_pages,
            google_analytics_id=config.GOOGLE_ANALYTICS_ID,
            google_adsense_id=config.GOOGLE_ADSENSE_ID,
            domain=config.DOMAIN,
            contact_email=config.CONTACT_EMAIL,
            relative_path='../',  # 用于调整相对路径，指向根目录
            sub_sitemap_url=f'content/topic_{topic_id}_sitemap.xml'  # 添加子站点地图链接
        )

        with open(f'web/{url}', 'w') as f:
            f.write(html_content)

# 首页每页显示的主题数量
themes_per_page = 10

# 生成首页
index_template = env.get_template('index.html')
topics = [(i, ' '.join(keywords[:3])) for i, keywords in enumerate(topic_keywords)]
total_theme_pages = (len(topics) // themes_per_page) + 1

for page in range(total_theme_pages):
    start_idx = page * themes_per_page
    end_idx = start_idx + themes_per_page
    page_topics = topics[start_idx:end_idx]
    url = f'index_page{page + 1}.html' if page > 0 else 'index.html'
    index_html_content = index_template.render(
        topics=page_topics,
        google_analytics_id=config.GOOGLE_ANALYTICS_ID,
        google_adsense_id=config.GOOGLE_ADSENSE_ID,
        domain=config.DOMAIN,
        contact_email=config.CONTACT_EMAIL,
        relative_path='./',
        current_page=page + 1,
        total_pages=total_theme_pages
    )

    with open(f'web/{url}', 'w') as f:
        f.write(index_html_content)

# 生成关于我们页面
about_template = env.get_template('about.html')
about_html_content = about_template.render(
    google_analytics_id=config.GOOGLE_ANALYTICS_ID,
    google_adsense_id=config.GOOGLE_ADSENSE_ID,
    domain=config.DOMAIN,
    contact_email=config.CONTACT_EMAIL,
    relative_path='./'  # 关于我们页相对路径
)

with open('web/about.html', 'w') as f:
    f.write(about_html_content)

# 生成联系我们页面
contact_template = env.get_template('contact.html')
contact_html_content = contact_template.render(
    google_analytics_id=config.GOOGLE_ANALYTICS_ID,
    google_adsense_id=config.GOOGLE_ADSENSE_ID,
    domain=config.DOMAIN,
    contact_email=config.CONTACT_EMAIL,
    relative_path='./'  # 联系我们页相对路径
)

with open('web/contact.html', 'w') as f:
    f.write(contact_html_content)

# 生成网站地图，分块处理
sitemap_template = env.get_template('sitemap.xml')
sitemap_index_template = env.get_template('sitemap_index.xml')

max_links_per_sitemap = 50000
sitemap_files = []

sitemap_entries = [
    {"loc": f"{config.DOMAIN}/index.html"}
] + [
    {"loc": f"{config.DOMAIN}/index_page{page + 1}.html"} for page in range(1, total_theme_pages)
] + [
    {"loc": f"{config.DOMAIN}/about.html"},
    {"loc": f"{config.DOMAIN}/contact.html"}
]

content_entries = [
    {"loc": f"{config.DOMAIN}/content/topic_{topic_id}_page{page + 1}.html"}
    for topic_id in range(len(grouped_tweets))
    for page in range((len(grouped_tweets[topic_id]) // tweets_per_page) + 1)
]

sitemap_entries.extend(content_entries)

for i in range(0, len(sitemap_entries), max_links_per_sitemap):
    chunk = sitemap_entries[i:i + max_links_per_sitemap]
    sitemap_xml_content = sitemap_template.render(entries=chunk)
    sitemap_file = f'web/sitemap_{i // max_links_per_sitemap + 1}.xml.gz'
    with gzip.open(sitemap_file, 'wt', encoding='utf-8') as f:
        f.write(sitemap_xml_content)
    sitemap_files.append(sitemap_file)

# 生成网站地图索引
sitemap_index_content = sitemap_index_template.render(sitemaps=[
    {"loc": f"{config.DOMAIN}/sitemap_{i + 1}.xml.gz"} for i in range(len(sitemap_files))
])

with open('web/sitemap_index.xml', 'w') as f:
    f.write(sitemap_index_content)
