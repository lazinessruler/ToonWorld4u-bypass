from flask import Flask, request, jsonify
import cloudscraper
import requests
import re
import json
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import sys

app = Flask(__name__)

def bypass_vshort(url):
    """
    Highly optimized vshort.xyz bypasser (Native Python)
    """
    start_all = time.time()
    result = {
        "status": "error",
        "original_url": url,
        "time": 0.0
    }
    
    parsed = urlparse(url)
    link_id = parsed.path.strip('/')
    
    if not link_id:
        result["error"] = "Could not extract link ID."
        return result
    
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Upgrade-Insecure-Requests": "1"
        })
        
        step1_url = f"https://www.2short.club/?link={link_id}"
        session.get(step1_url, headers={"Referer": url}, timeout=10)
        
        step5_url = f"https://vshort.xyz/{link_id}"
        resp = session.get(step5_url, headers={"Referer": f"https://finance.vshort.xyz/?link={link_id}"}, timeout=10)
        html = resp.text
        
        def ext(pattern):
            match = re.search(pattern, html)
            return match.group(1) if match else ""
        
        payload = {
            "_method": "POST",
            "_csrfToken": ext(r'name="_csrfToken".*?value="([^"]+)"'),
            "ad_form_data": ext(r'name="ad_form_data".*?value="([^"]+)"'),
            "_Token[fields]": ext(r'name="_Token\[fields\]".*?value="([^"]+)"'),
            "_Token[unlocked]": ext(r'name="_Token\[unlocked\]".*?value="([^"]+)"'),
        }
        
        if not payload["ad_form_data"]:
            match = re.search(r'ad_form_data\s*=\s*"([^"]+)"', html)
            if match: 
                payload["ad_form_data"] = match.group(1)
        
        if not payload["ad_form_data"]:
            result["error"] = "Could not extract security tokens."
            result["time"] = round(time.time() - start_all, 2)
            return result
        
        headers = {
            "Origin": "https://vshort.xyz",
            "Referer": step5_url,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }
        
        final_resp = session.post("https://vshort.xyz/links/go", data=payload, headers=headers, timeout=25)
        
        try:
            data = final_resp.json()
            result["time"] = round(time.time() - start_all, 2)
            if data.get('status') == 'success':
                result["status"] = "success"
                result["bypassed_url"] = data.get('url')
                return result
            result["error"] = data.get('message', 'Unknown server error')
        except:
            result["error"] = f"Failed to parse server response: {final_resp.text[:50]}"
            
    except Exception as e:
        result["error"] = str(e)
        result["time"] = round(time.time() - start_all, 2)
    
    return result

def get_shortener_link(url, index=4):
    """
    Resolve Toonworld4all redirect and detect shortener
    """
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )
    scraper.cookies.set("shortener_index", str(index))
    scraper.cookies.set("popup_expiry", "9999999999999")
    scraper.cookies.set("user_system_preference", "manual")
    
    try:
        resp = scraper.get(url, allow_redirects=False, timeout=20)
        found_url = None
        if resp.status_code in (301, 302, 303, 307, 308):
            found_url = resp.headers.get("Location")
        if not found_url and resp.status_code == 200:
            found_url = resp.url
        return found_url
    except:
        return None

def scrape_toonworld(url, name="@Blaze_UpdateZ"):
    start_time = time.time()
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    
    try:
        response = scraper.get(url, timeout=30)
        if response.status_code != 200:
            return {"status": "error", "error": f"Failed to load page ({response.status_code})", "url": url}
        
        if "archive.toonworld4all.me/episode/" in url:
            res = process_episode(url, response.text)
        elif "toonworld4all.me" in url:
            res = process_series(url, response.text)
        else:
            return {"status": "error", "error": "Unsupported URL format for scraping.", "url": url}
        
        res["time"] = round(time.time() - start_time, 2)
        res["requester"] = name
        return res
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url, "time": round(time.time() - start_time, 2)}

def process_episode(url, html):
    match = re.search(r'window\.PROPS\s*=\s*({.*?});', html, re.DOTALL)
    if not match: 
        return {"status": "error", "error": "Could not find data script."}
    
    try:
        data = json.loads(match.group(1))
        episode_data = data.get('data', {}).get('data', {})
        metadata = episode_data.get('metadata', {})
        encodes = episode_data.get('encodes', [])
        
        title = f"{metadata.get('show', 'Unknown')} - S{metadata.get('season', 1):02d}E{metadata.get('episode', 1):02d} - {metadata.get('name', '')}"
        
        qualities = []
        for enc in encodes:
            readable = enc.get('readable', {})
            q_title = f"{readable.get('codec', enc.get('resolution', 'Unknown'))} ({readable.get('size', 'Unknown')})"
            links = []
            for f in enc.get('files', []):
                host = f.get('host', 'Unknown')
                link = f.get('link', '')
                if link.startswith('/'): 
                    link = "https://archive.toonworld4all.me" + link
                links.append({'name': host, 'url': link})
            qualities.append({'title': q_title, 'links': links})
        
        return {
            "status": "success",
            "type": "episode",
            "original_url": url,
            "title": title,
            "qualities": qualities
        }
    except Exception as e:
        return {"status": "error", "error": f"Parse Error: {str(e)}"}

def process_series(url, html):
    soup = BeautifulSoup(html, 'html.parser')
    title_el = soup.select_one('.entry-title') or soup.select_one('h1')
    page_title = title_el.get_text(strip=True) if title_el else "Unknown Series"
    
    episodes = []
    items = soup.select('.mks_accordion_item') or soup.select('.wp-block-meks-mks-accordion-item')
    
    for i, item in enumerate(items):
        title_head = item.select_one('.mks_accordion_item_title') or item.select_one('.mks_accordion_heading')
        ep_title = title_head.get_text(strip=True) if title_head else f"Episode {i+1}"
        link_el = item.select_one('a[href*="archive.toonworld4all.me/episode/"]')
        if link_el and link_el.get('href'):
            episodes.append({'title': ep_title, 'url': link_el['href']})
    
    return {
        "status": "success",
        "type": "series",
        "original_url": url,
        "title": page_title,
        "episodes": episodes
    }

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "active",
        "message": "Toonworld4all API is running",
        "endpoints": {
            "GET /": "This help message",
            "GET /bypass?url=<toonworld_url>": "Bypass Toonworld URL",
            "GET /health": "Health check"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

@app.route('/bypass', methods=['GET'])
def bypass():
    url = request.args.get('url')
    name = request.args.get('name', '@Blaze_UpdateZ')
    
    if not url:
        return jsonify({"status": "error", "error": "URL parameter is required"}), 400
    
    if "vshort.xyz" in url:
        res = bypass_vshort(url)
    elif "archive.toonworld4all.me/redirect/" in url:
        resolved = get_shortener_link(url, index=4)
        if resolved and "vshort.xyz" in resolved:
            res = bypass_vshort(resolved)
        else:
            res = {"status": "success", "type": "redirect", "original_url": url, "resolved_url": resolved}
    else:
        res = scrape_toonworld(url, name)
    
    return jsonify(res)

# Vercel serverless function handler
def handler(event, context):
    return app(event, context)

if __name__ == '__main__':
    app.run(debug=True)
