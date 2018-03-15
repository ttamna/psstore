# -*- coding: utf-8 -*-
from __future__ import print_function

import re
import codecs
import datetime

import tweepy
import requests
from requests.compat import urljoin
from bs4 import BeautifulSoup as Soup

import secret


def error_safe_print(msg):
    try:
        print(msg)
    except (IOError, UnicodeEncodeError):
        pass

#################### about output format ####################
html_format = u"""<!DOCTYPE html>
<html>
<head>
    <title>PSN 한국 혜자 할인정보</title>
    <!-- 합쳐지고 최소화된 최신 CSS -->
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/css/bootstrap.min.css">
    <!-- 부가적인 테마 -->
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/css/bootstrap-theme.min.css">
    <style>
    img {{
      max-width:100%;
      max-height:100%;
    }}
    .rrow {{
      height:375px;
    }}
    .grid-cell {{
        padding:10px;
        background-color:#262b34;
        color:#fefefe;
        height:345px;
        margin-top:10px;
    }}
    .price {{
        color:#B3B3B3;
    }}
    .price_psn {{
        color:#FFC926;
    }}
    .psn_bg {{
        background-color:#002055;
    }}
    </style>
<head>
<body>
<div class="container psn_bg">
  {body_content}
</div>

<script src="https://ajax.googleapis.com/ajax/libs/jquery/1.11.2/jquery.min.js"></script>
<script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/js/bootstrap.min.js"></script>
</body>
</html>
"""


hyeja_format = u"""
  <div class="col-lg-2 col-md-2 col-sm-4 col-xs-4 text-center">
  <a href="{url}">
    <div class="grid-cell">
        <div><img src="{img_url}"/></div>
        <div>{title}</div>
        <div class="price"><strike>{price_before}</strike></div>
        <div class="price">{price_after} ({dr}%)</div>
        <div class="price_psn">{price_after_psn} ({final_dr}%, PSN:{psn_dr}%)</div>
        <div>metascore: {metascore}</div>
        <div>userscore: {userscore}</div>
    </div>
  </a>
  </div>

""" # TODO: 할인율은 뱃지로 표현하는게 좋을듯

def to_html_grid_format(divs):
    n_cells = 6

    ret_grid_format = ""
    row = u'<div class="row rrow">{cells}</div>\n'
    div_len = len(divs)
    for i in range(0, div_len, n_cells):
        ret_grid_format += row.format(cells=u"".join(divs[i:min(div_len-1, i+n_cells)]))

    return ret_grid_format

#################### about output format ####################


#################### about metacritic score ####################
# TODO: goty 여부도 표시하면 좋을듯
# 한국 psn에는 게임이름이 한글로 나와서 metacritic score 점수 조회 어려움
# https://store.playstation.com/ko-kr/product/UP1018-CUSA04408_00-ASIAPLACEHOLDER1
# 가운데 ko-kr을 en-us로 바꾸면, 영어 이름 얻을 수 있음
# 미국 스토어에서 이름 뽑은 다음에, 구글에 메타크리틱 페이지 검색해서 처리함

header = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.116 Safari/537.36', "Connection":"close"}

def get_en_title_name(ko_game_url):
    # get english title name
    en_game_url = ko_game_url.replace('ko-kr', 'en-us')
    res = requests.get(en_game_url, headers={"Connection":"close"})
    if res.status_code != 200: return ''
    
    soup = Soup(res.content, "html.parser")
    t_ = soup.find("meta", {"property":"og:title"})
    if t_ == None: return ''
    
    title = t_.get('content')
    return title

def get_metalink_from_google(searchfor):
    link = 'https://google.co.kr/search'    
    payload = {'q': searchfor}
    res = requests.get(link, headers=header, params=payload)

    soup = Soup(res.content, "html.parser")
    anchors = soup.select('h3.r > a')
    for anchor in anchors:
        url = anchor.get('href')        
        if "www.metacritic.com" in url:
            return url
    return ''

def get_metainfo_from_metapage(metalink):
    res = requests.get(metalink, headers=header)
    if res.status_code != 200: return ''

    soup = Soup(res.content, 'html.parser')
    metascore = soup.find("span", {"itemprop":"ratingValue"})
    userscore = soup.select_one('div.userscore_wrap.feature_userscore > a > div')
    try:
        metascore = int(metascore.get_text())
    except (ValueError, AttributeError):
        metascore = -1
    try:
        userscore = userscore.get_text()
    except (ValueError, AttributeError):
        userscore = -1

    return metascore, userscore

meta_visited = {}
google_searched = {}
url_title_map = {}
def get_metascore(ko_game_url):
    """ metascore, userscore 알아내서 반환, 못알아내면, (-1, -1) 반환
    
    :param ko_game_url: game url(psn_korea)
    :type ko_game_url: str
    """
    # ko_game_url to title
    if ko_game_url not in url_title_map.keys():
        title = get_en_title_name(ko_game_url)
        url_title_map[ko_game_url] = title
    else:
        title = url_title_map[ko_game_url]
    if title == u'':
        return (-1, -1)

    # title to metacritic link
    if title not in google_searched.keys():
        error_safe_print(u"[+] {}의 metacritic 페이지를 검색하는 중..".format(title))
        metalink = get_metalink_from_google(title+u" metacritic")
        google_searched[title] = metalink
    else:
        metalink = google_searched[title]
    if metalink == "":
        return (-1, -1)

    # metalink to (metascore, userscore)
    if metalink not in meta_visited.keys():
        error_safe_print(u"[+] {}의 metacritic 점수를 확인하는 중..".format(title))
        ms, us = get_metainfo_from_metapage(metalink)
        meta_visited[metalink]= (ms, us)
    else:
        ms, us = meta_visited[metalink]
    
    return (ms, us)

#################### about metacritic score ####################
def write_twit(msg):
    """ Twitt
    
    :param msg: msg to twitt
    :type msg: str
    """
    auth = tweepy.OAuthHandler(secret.consumer_key, secret.consumer_secret)
    auth.set_access_token(secret.access_token, secret.access_token_secret)
    api = tweepy.API(auth)
    api.update_status(msg)

def get_reg_price(price_str):
    """ '123,456원' -> 123456
    
    :param price_str: original
    :type price_str: str
    :return: price
    :rtype: int
    """

    _pr = price_str.replace(',','')
    price_int = int(re.search('\d+', _pr).group())
    return price_int

def query_ifitis_heyja(url):
    """ psn 회원 추가할인율이 높은지 검사

    호라이즌 제로던 사례:
      기본할인 30% 이고 PSN 회원은 5% 추가할인해서 35%인데,
      실수로 추가 35%를 해서 총 65% 할인이됨
      (3만얼마로 할인하려던게 1만얼마로 나옴..)
    
    :param url: 게임 상세페이지
    :type url: str
    :return: PSN 추가할인이 특정값 이상이면, True 반환
    :rtype: bool
    """

    res = requests.get(url, headers={"Connection":"close"})
    if res.status_code != 200:
        return False, 0
    soup = Soup(res.content, 'html.parser')
    has_psn_price = soup.select('.psPlusLabel')
    if has_psn_price == []:
        return False, 0

    _sale = soup.select_one('.price-display__price__label').get_text()
    sale = int(re.search('\d+', _sale).group())
    if sale >= 10:
        return True, sale
    return False, sale

def scrap(url):
    """ 할인 페이지 요청, 파싱 시작하고, 좋은 가격이면 알림
    
    할인페이지는 페이지당 타이틀 30개 최대임.
    다음 페이지가 있으면, 다음 페이지 요청 (재귀)

    :param url: PSN 할인페이지
    :type url: str
    """
    error_safe_print(u"[+] Processing URL: {}".format(url))
    res = requests.get(url, headers={"Connection":"close"})
    if res.status_code!=200:
        return None
    soup = Soup(res.content, 'html.parser')

    ret_hyejas = []
    cards = soup.select('.grid-cell')  # games
    for card in cards:
        dr = card.select_one('.discount-badge__message')
        if dr is None:
            continue
        dr = dr.get_text() # discount
        dr = int(re.search('\d+', dr).group())
        
        title = card.select_one('.grid-cell__title').get_text()
        price_before = get_reg_price(card.select_one('.price').get_text()) # before discount
        price_after = get_reg_price(card.select_one('.price-display__price').get_text()) # after discount
        game_link = urljoin(url, card.select_one('.internal-app-link').get('href'))
        
        metascore, userscore = get_metascore(game_link) # 메타크리틱 점수 확인
        if metascore < 70 or userscore < 7:
            continue

        is_heyja, psn_dr = query_ifitis_heyja(game_link)
        final_dr = dr + psn_dr

        if is_heyja or final_dr >= 50:
            img_url = urljoin(url, card.select('img')[1].get('src'))

            div_element = hyeja_format.format(
                title=title,
                url=game_link,
                price_before=price_before,
                price_after=price_after,
                dr=dr, psn_dr = psn_dr,
                price_after_psn= int(price_before-(price_before*(final_dr/100.0))),
                final_dr=final_dr,
                img_url=img_url,
                metascore=metascore, userscore=userscore
            )
            ret_hyejas.append(div_element)
        
    # continue to next page
    next_p = soup.find(class_="paginator-control__next")

    if (next_p is not None) and ('paginator-control__arrow-navigation--disabled' not in next_p.get('class')):
        next_p = urljoin(url, next_p.get('href'))
        return ret_hyejas + scrap(next_p)
    else:
        return ret_hyejas

def main():
    url = 'https://store.playstation.com/ko-kr/grid/STORE-MSF86012-SPECIALOFFER/1'
    
    hyejas = scrap(url)
    body_content = to_html_grid_format(hyejas)

    time_format_now = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S%m")
    result_fn = time_format_now+"_psstore.html"
    with codecs.open(result_fn, "w", encoding='utf8') as f:
        f.write(html_format.format(body_content=body_content))
    
    error_safe_print("Complete")


if __name__ == "__main__":
    main()
