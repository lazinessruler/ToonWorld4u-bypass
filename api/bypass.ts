import { VercelRequest, VercelResponse } from '@vercel/node';
import axios, { AxiosInstance } from 'axios';
import * as cheerio from 'cheerio';
import * as url from 'url';

// Types
interface BypassResult {
  status: 'success' | 'error';
  original_url: string;
  bypassed_url?: string;
  error?: string;
  time: number;
  type?: string;
  title?: string;
  qualities?: Quality[];
  episodes?: Episode[];
  requester?: string;
}

interface Quality {
  title: string;
  links: Link[];
}

interface Link {
  name: string;
  url: string;
}

interface Episode {
  title: string;
  url: string;
}

interface VShortPayload {
  _method: string;
  _csrfToken: string;
  ad_form_data: string;
  '_Token[fields]': string;
  '_Token[unlocked]': string;
}

interface VShortResponse {
  status: string;
  url?: string;
  message?: string;
}

// Constants
const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
const DEFAULT_REQUESTER = '@Blaze_UpdateZ';

// Create axios instance with default headers
function createClient(): AxiosInstance {
  return axios.create({
    timeout: 8000,
    headers: {
      'User-Agent': USER_AGENT,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate, br',
      'Connection': 'keep-alive',
      'Upgrade-Insecure-Requests': '1'
    },
    maxRedirects: 5
  });
}

// Extract text using regex
function extractText(html: string, pattern: RegExp): string {
  const match = html.match(pattern);
  return match ? match[1] : '';
}

// Bypass vshort.xyz
async function bypassVShort(url: string): Promise<BypassResult> {
  const startTime = Date.now();
  const result: BypassResult = {
    status: 'error',
    original_url: url,
    time: 0
  };

  try {
    const parsed = new URL(url);
    const linkId = parsed.pathname.replace(/^\//, '');
    
    if (!linkId) {
      result.error = 'Could not extract link ID';
      return result;
    }

    const client = createClient();

    // Step 1: Visit 2short.club
    await client.get(`https://www.2short.club/?link=${linkId}`, {
      headers: { Referer: url }
    });

    // Step 2: Get main page
    const mainPageUrl = `https://vshort.xyz/${linkId}`;
    const mainPageRes = await client.get(mainPageUrl, {
      headers: { Referer: `https://finance.vshort.xyz/?link=${linkId}` }
    });
    
    const html = mainPageRes.data;

    // Extract tokens
    const csrfToken = extractText(html, /name="_csrfToken".*?value="([^"]+)"/);
    let adFormData = extractText(html, /name="ad_form_data".*?value="([^"]+)"/);
    const tokenFields = extractText(html, /name="_Token\[fields\]".*?value="([^"]+)"/);
    const tokenUnlocked = extractText(html, /name="_Token\[unlocked\]".*?value="([^"]+)"/);

    // Alternative pattern for ad_form_data
    if (!adFormData) {
      const altMatch = html.match(/ad_form_data\s*=\s*"([^"]+)"/);
      adFormData = altMatch ? altMatch[1] : '';
    }

    if (!adFormData) {
      result.error = 'Could not extract security tokens';
      result.time = (Date.now() - startTime) / 1000;
      return result;
    }

    // Prepare payload
    const payload: VShortPayload = {
      _method: 'POST',
      _csrfToken: csrfToken,
      ad_form_data: adFormData,
      '_Token[fields]': tokenFields,
      '_Token[unlocked]': tokenUnlocked
    };

    // Make final request
    const finalRes = await client.post('https://vshort.xyz/links/go', 
      new URLSearchParams(payload as any).toString(),
      {
        headers: {
          'Origin': 'https://vshort.xyz',
          'Referer': mainPageUrl,
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
      }
    );

    const data = finalRes.data as VShortResponse;
    
    if (data.status === 'success' && data.url) {
      result.status = 'success';
      result.bypassed_url = data.url;
    } else {
      result.error = data.message || 'Unknown error';
    }

  } catch (error: any) {
    if (error.code === 'ECONNABORTED') {
      result.error = 'Request timeout';
    } else {
      result.error = error.message?.substring(0, 100) || 'Unknown error';
    }
  }

  result.time = (Date.now() - startTime) / 1000;
  return result;
}

// Process episode page
function processEpisode(url: string, html: string): BypassResult {
  try {
    const scriptMatch = html.match(/window\.PROPS\s*=\s*({.*?});/s);
    if (!scriptMatch) {
      return { status: 'error', original_url: url, error: 'Could not find data script', time: 0 };
    }

    const data = JSON.parse(scriptMatch[1]);
    const episodeData = data.data?.data || {};
    const metadata = episodeData.metadata || {};
    const encodes = episodeData.encodes || [];

    const title = `${metadata.show || 'Unknown'} - S${String(metadata.season || 1).padStart(2, '0')}E${String(metadata.episode || 1).padStart(2, '0')}${metadata.name ? ` - ${metadata.name}` : ''}`;

    const qualities: Quality[] = [];
    
    for (const enc of encodes.slice(0, 3)) {
      const readable = enc.readable || {};
      let qTitle = readable.codec || enc.resolution || 'Unknown';
      if (readable.size) {
        qTitle += ` (${readable.size})`;
      }

      const links: Link[] = [];
      for (const f of (enc.files || []).slice(0, 2)) {
        let linkUrl = f.link || '';
        if (linkUrl && linkUrl.startsWith('/')) {
          linkUrl = 'https://archive.toonworld4all.me' + linkUrl;
        }
        if (linkUrl) {
          links.push({ name: f.host || 'Unknown', url: linkUrl });
        }
      }

      if (links.length > 0) {
        qualities.push({ title: qTitle, links });
      }
    }

    return {
      status: 'success',
      type: 'episode',
      original_url: url,
      title: title,
      qualities: qualities,
      time: 0
    };

  } catch (error: any) {
    return { 
      status: 'error', 
      original_url: url, 
      error: `Parse Error: ${error.message?.substring(0, 50)}`,
      time: 0 
    };
  }
}

// Process series page
function processSeries(url: string, html: string): BypassResult {
  try {
    const $ = cheerio.load(html);
    
    const titleEl = $('.entry-title').first() || $('h1').first();
    const pageTitle = titleEl.text().trim().substring(0, 100) || 'Unknown Series';

    const episodes: Episode[] = [];
    
    // Try different selectors
    const items = $('.mks_accordion_item, .wp-block-meks-mks-accordion-item');
    
    items.each((i, el) => {
      if (i >= 10) return false; // Limit to 10 episodes
      
      const titleHead = $(el).find('.mks_accordion_item_title, .mks_accordion_heading').first();
      const epTitle = titleHead.text().trim() || `Episode ${i + 1}`;
      
      const linkEl = $(el).find('a[href*="archive.toonworld4all.me/episode/"]').first();
      const episodeUrl = linkEl.attr('href');
      
      if (episodeUrl) {
        episodes.push({
          title: epTitle.substring(0, 50),
          url: episodeUrl
        });
      }
    });

    return {
      status: 'success',
      type: 'series',
      original_url: url,
      title: pageTitle,
      episodes: episodes,
      time: 0
    };

  } catch (error: any) {
    return { 
      status: 'error', 
      original_url: url, 
      error: `Parse Error: ${error.message?.substring(0, 50)}`,
      time: 0 
    };
  }
}

// Scrape Toonworld
async function scrapeToonworld(url: string): Promise<BypassResult> {
  const startTime = Date.now();
  
  try {
    const client = createClient();
    const response = await client.get(url, { timeout: 8000 });

    if (response.status !== 200) {
      return {
        status: 'error',
        original_url: url,
        error: `Failed to load page (${response.status})`,
        time: (Date.now() - startTime) / 1000
      };
    }

    let result: BypassResult;
    if (url.includes('archive.toonworld4all.me/episode/')) {
      result = processEpisode(url, response.data);
    } else if (url.includes('toonworld4all.me')) {
      result = processSeries(url, response.data);
    } else {
      result = {
        status: 'error',
        original_url: url,
        error: 'Unsupported URL format',
        time: (Date.now() - startTime) / 1000
      };
    }

    result.time = (Date.now() - startTime) / 1000;
    return result;

  } catch (error: any) {
    return {
      status: 'error',
      original_url: url,
      error: error.message?.substring(0, 100) || 'Unknown error',
      time: (Date.now() - startTime) / 1000
    };
  }
}

// Main handler
export default async function handler(req: VercelRequest, res: VercelResponse) {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  // Handle preflight
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // Only allow GET
  if (req.method !== 'GET') {
    return res.status(405).json({ 
      status: 'error', 
      error: 'Method not allowed. Use GET.' 
    });
  }

  const { url, name = DEFAULT_REQUESTER } = req.query;

  // Home endpoint
  if (!url) {
    return res.status(200).json({
      status: 'active',
      message: 'Toonworld4all API (TypeScript)',
      version: '2.0.0',
      endpoints: {
        'GET /api/bypass?url=<url>': 'Bypass Toonworld URL',
        'GET /api/bypass?url=<url>&name=<name>': 'Bypass with custom name',
        'GET /health': 'Health check'
      },
      repository: 'https://github.com/lazinessruler/ToonWorld4u-bypass'
    });
  }

  // Health check
  if (url === 'health') {
    return res.status(200).json({
      status: 'healthy',
      timestamp: Date.now() / 1000
    });
  }

  // Validate URL
  if (typeof url !== 'string') {
    return res.status(400).json({
      status: 'error',
      error: 'URL must be a string'
    });
  }

  // Process URL
  let result: BypassResult;
  
  if (url.includes('vshort.xyz')) {
    result = await bypassVShort(url);
  } else if (url.includes('toonworld4all.me') || url.includes('archive.toonworld4all.me')) {
    result = await scrapeToonworld(url);
    result.requester = typeof name === 'string' ? name : DEFAULT_REQUESTER;
  } else {
    result = {
      status: 'error',
      original_url: url,
      error: 'Unsupported URL. Only toonworld4all.me and vshort.xyz URLs are supported',
      time: 0
    };
  }

  return res.status(200).json(result);
}