# -*- coding: utf-8 -*-
from __future__ import print_function

import re
import tweepy
import requests
from requests.compat import urljoin
from bs4 import BeautifulSoup as Soup

import secret

hyeja_format = """[HYEJA] : {title}
  - {url}
  할인전 : {price_before}
  할인후 : {price_after} ({dr}%)
  PSN 할인후 : {price_after_psn} ({final_dr}% <- +psn:{psn_dr}%)

"""

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
    :return: PSN 추가할인이 특정 수치 이상이면, True 반환
    :rtype: bool
    """

    res = requests.get(url)
    if res.status_code != 200:
        return False, 0
    soup = Soup(res.content, 'html.parser')
    has_psn_price = soup.select('.psPlusLabel')
    if has_psn_price == []:
        return False, 0

    _sale = soup.select_one('.price-display__price__label').get_text()
    sale = int(re.search('\d+', _sale).group())
    if sale > 30:
        return True, sale
    return False, 0

def scrape(url):
    """ 할인 페이지 요청, 파싱 시작하고, 좋은 가격이면 알림
    
    할인페이지는 페이지당 타이틀 30개 최대임.
    다음 페이지가 있으면, 다음 페이지 요청 (재귀)

    :param url: PSN 할인페이지
    :type url: str
    """

    res = requests.get(url)
    if res.status_code!=200:
        return None
    soup = Soup(res.content, 'html.parser')

    cards = soup.select('.grid-cell')  # games
    for card in cards:
        dr = card.select_one('.discount-badge__message')
        if dr is None:
            continue
        dr = dr.get_text() # discount
        dr = int(re.search('\d+', dr).group())
        price_before = card.select_one('.price').get_text() # before discount
        price_after = card.select_one('.price-display__price').get_text()
        title = card.select_one('.grid-cell__title').get_text()

        #print(title, price_before, u'--{}-->'.format(dr), price_after)
        price_before = get_reg_price(price_before)
        price_after = get_reg_price(price_after)

        detail_link = urljoin(url, card.select_one('.internal-app-link').get('href'))
        is_heyja, psn_dr = query_ifitis_heyja(detail_link)

        if is_heyja: # 싸다
            # TODO: 인기 있는 게임인지 확인 필요
            # TODO: '총 할인율, 특정 수치 이상' 조건을 줄지 고민
            
            final_dr = dr+psn_dr
            msg = hyeja_format.format(
                title=title,
                url=detail_link,
                price_before=price_before,
                price_after=price_after,
                dr=dr, psn_dr = psn_dr,
                price_after_psn= price_before*(final_dr/100),
                final_dr=final_dr
            )
            print(msg)

            img_url = urljoin(url, card.select('img')[1].get('src'))
            #write_twit("Hello twitter")


    # continue to next page
    next_p = soup.find(class_="paginator-control__next")

    if (next_p is not None) and ('paginator-control__arrow-navigation--disabled' not in next_p.get('class')):
        next_p = urljoin(url, next_p.get('href'))
        scrape(next_p)


def main():
    url = 'https://store.playstation.com/ko-kr/grid/STORE-MSF86012-SPECIALOFFER/1'
    scrape(url)

if __name__ == "__main__":
    main()