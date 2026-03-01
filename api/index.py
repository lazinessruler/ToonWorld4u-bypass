from flask import Flask, request, jsonify
import requests
import re
import json
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

# Simple requests session without cloudscraper for Vercel
def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })
    return session

def bypass_vshort(url):
    """
    Optimized vshort.xyz bypasser for Vercel
    """
    start_all = time.time()
    result = {
        "status": "error",
        "original_url": url,
        "time": 0.0
    }
    
    try:
        parsed = urlparse(url)
        link_id = parsed.path.strip('/')
        
        if not link_id:
            result["error"] = "Could not extract link ID."
            return result
        
        session = get_session()
        
        # Step 1: Visit 2short.club
        step1_url = f"https://www.2short.club/?link={link_id}"
        session.get(step1_url, timeout=5)
        
        # Step 2: Get the main page
        step5_url = f"https://vshort.xyz/{link_id}"
        resp = session.get(step5_url, timeout=5)
        html = resp.text
        
        # Extract tokens
        def extract_token(pattern):
            match = re.search(pattern, html, re.DOTALL)
            return match.group(1) if match else ""
        
        csrf_token = extract_token(r'name="_csrfToken".*?value="([^"]+)"')
        ad_form_data = extract_token(r'name="ad_form_data".*?value="([^"]+)"')
        token_fields = extract_token(r'name="_Token\[fields\]".*?value="([^"]+)"')
        token_unlocked = extract_token(r'name="_Token\[unlocked\]".*?value="([^"]+)"')
        
        # Try alternative pattern for ad_form_data
        if not ad_form_data:
            alt_match = re.search(r'ad_form_data\s*=\s*"([^"]+)"', html)
            if alt_match:
                ad_form_data = alt_match.group(1)
        
        if not ad_form_data:
            result["error"] = "Could not extract security tokens."
            result["time"] = round(time.time() - start_all, 2)
            return result
        
        # Prepare payload
        payload = {
            "_method": "POST",
            "_csrfToken": csrf_token,
            "ad_form_data": ad_form_data,
            "_Token[fields]": token_fields,
            "_Token[unlocked]": token_unlocked,
        }
        
        # Make the final request
        headers = {
            "Origin": "https://vshort.xyz",
            "Referer": step5_url,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }
        
        final_resp = session.post(
            "https://vshort.xyz/links/go", 
            data=payload, 
            headers=headers, 
            timeout=5
        )
        
        if final_resp.status_code == 200:
            try:
                data = final_resp.json()
                if data.get('status') == 'success' and data.get('url'):
                    result["status"] = "success"
                    result["bypassed_url"] = data.get('url')
                else:
                    result["error"] = data.get('message', 'Unknown error')
            except:
                result["error"] = "Invalid JSON response"
        else:
            result["error"] = f"HTTP {final_resp.status_code}"
            
    except requests.exceptions.Timeout:
        result["error"] = "Request timeout"
    except Exception as e:
        result["error"] = str(e)[:100]
    
    result["time"] = round(time.time() - start_all, 2)
    return result

def scrape_toonworld(url):
    """
    Scrape Toonworld4all without cloudscraper
    """
    start_time = time.time()
    
    try:
        session = get_session()
        response = session.get(url, timeout=8)
        
        if response.status_code != 200:
            return {
                "status": "error", 
                "error": f"Failed to load page ({response.status_code})", 
                "url": url
            }
        
        if "archive.toonworld4all.me/episode/" in url:
            result = process_episode(url, response.text)
        elif "toonworld4all.me" in url:
            result = process_series(url, response.text)
        else:
            return {
                "status": "error", 
                "error": "Unsupported URL format", 
                "url": url
            }
        
        result["time"] = round(time.time() - start_time, 2)
        return result
        
    except Exception as e:
        return {
            "status": "error", 
            "error": str(e)[:100], 
            "url": url, 
            "time": round(time.time() - start_time, 2)
        }

def process_episode(url, html):
    """Process episode page"""
    match = re.search(r'window\.PROPS\s*=\s*({.*?});', html, re.DOTALL)
    if not match:
        return {"status": "error", "error": "Could not find data script"}
    
    try:
        data = json.loads(match.group(1))
        episode_data = data.get('data', {}).get('data', {})
        metadata = episode_data.get('metadata', {})
        encodes = episode_data.get('encodes', [])
        
        title = f"{metadata.get('show', 'Unknown')} - S{metadata.get('season', 1):02d}E{metadata.get('episode', 1):02d}"
        if metadata.get('name'):
            title += f" - {metadata.get('name')}"
        
        qualities = []
        for enc in encodes[:3]:  # Limit to 3 qualities to save space
            readable = enc.get('readable', {})
            q_title = f"{readable.get('codec', enc.get('resolution', 'Unknown'))}"
            if readable.get('size'):
                q_title += f" ({readable.get('size')})"
            
            links = []
            for f in enc.get('files', [])[:2]:  # Limit to 2 links per quality
                host = f.get('host', 'Unknown')
                link = f.get('link', '')
                if link and link.startswith('/'):
                    link = "https://archive.toonworld4all.me" + link
                if link:
                    links.append({'name': host, 'url': link})
            
            if links:
                qualities.append({'title': q_title, 'links': links})
        
        return {
            "status": "success",
            "type": "episode",
            "original_url": url,
            "title": title,
            "qualities": qualities
        }
    except Exception as e:
        return {"status": "error", "error": f"Parse Error: {str(e)[:50]}"}

def process_series(url, html):
    """Process series page"""
    soup = BeautifulSoup(html, 'html.parser')
    title_el = soup.select_one('.entry-title') or soup.select_one('h1')
    page_title = title_el.get_text(strip=True)[:100] if title_el else "Unknown Series"
    
    episodes = []
    items = soup.select('.mks_accordion_item') or soup.select('.wp-block-meks-mks-accordion-item')
    
    for i, item in enumerate(items[:10]):  # Limit to 10 episodes
        title_head = item.select_one('.mks_accordion_item_title') or item.select_one('.mks_accordion_heading')
        ep_title = title_head.get_text(strip=True) if title_head else f"Episode {i+1}"
        link_el = item.select_one('a[href*="archive.toonworld4all.me/episode/"]')
        if link_el and link_el.get('href'):
            episodes.append({
                'title': ep_title[:50], 
                'url': link_el['href']
            })
    
    return {
        "status": "success",
        "type": "series",
        "original_url": url,
        "title": page_title,
        "episodes": episodes[:10]  # Limit episodes
    }

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "active",
        "message": "Toonworld4all API",
        "version": "1.0.0",
        "endpoints": {
            "GET /bypass?url=<url>": "Bypass Toonworld URL",
            "GET /health": "Health check"
        },
        "note": "This is a serverless API with 10s timeout limit"
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time()
    })

@app.route('/bypass', methods=['GET'])
def bypass():
    url = request.args.get('url')
    
    if not url:
        return jsonify({
            "status": "error", 
            "error": "URL parameter is required"
        }), 400
    
    # Handle different URL types
    if "vshort.xyz" in url:
        result = bypass_vshort(url)
    elif "toonworld4all.me" in url or "archive.toonworld4all.me" in url:
        result = scrape_toonworld(url)
    else:
        result = {
            "status": "error",
            "error": "Unsupported URL. Only toonworld4all.me and vshort.xyz URLs are supported",
            "url": url
        }
    
    return jsonify(result)

# For Vercel serverless
def handler(request):
    return app(request)

# For local development
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
