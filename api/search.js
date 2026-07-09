// api/search.js — Smart Search с Claude AI
// Взема естествен език, връща кои продукти да се покажат + кратко обяснение

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { query, products, lang = 'bg' } = req.body;
  if (!query || !products) return res.status(400).json({ error: 'Missing query or products' });

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return res.status(500).json({ error: 'ANTHROPIC_API_KEY липсва в Vercel' });

  const catalog = products.map(p => ({
    id: p.id,
    name_bg: p.name_bg,
    verdict: p.verdict,
    discount_pct: p.discount_pct,
    current_price: p.current_price,
    best_chain: p.best_chain,
  }));

  const systemPrompt = lang === 'bg'
    ? `Ти си асистент на SaveCheck — приложение, което следи цени в български супермаркети (Lidl, Kaufland, Billa, Fantastico) и проверява дали промоциите са реални според EU Omnibus директивата.

Разполагаш с каталог от ${catalog.length} продукта с текущи цени и присъди (green=реална промоция, yellow=обичайна цена, red=фалшива промоция).

Твоята задача: разбери какво търси потребителят и върни JSON с кои продукти да се покажат и кратко обяснение.

Правила:
- Отговаряй САМО с валиден JSON, без markdown, без обяснения извън JSON
- Ако питането е за храна/готвене — намери свързаните продукти от каталога
- Ако питането е "евтино", "промоции", "реални" — върни само green продукти
- Ако питането е за верига (Lidl, Kaufland и др.) — върни продуктите с best_chain = тази верига
- Ако питането е извън обхвата на цени/пазаруване — върни празен масив и обясни накратко
- message-ът трябва да е кратък, приятелски, на български, макс 1-2 изречения

Формат на отговора:
{
  "ids": ["milk", "eggs"],
  "message": "Яйцата са с реална промоция тази седмица 🟢"
}`
    : `You are a SaveCheck assistant tracking supermarket prices.
Return ONLY valid JSON: { "ids": [...], "message": "..." }
Match products from the catalog to the user's natural language query.`;

  const userPrompt = `Каталог: ${JSON.stringify(catalog)}\n\nПитане: "${query}"`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 256,
        system: systemPrompt,
        messages: [{ role: 'user', content: userPrompt }],
      }),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message || `HTTP ${response.status}`);

    const text = data.content?.[0]?.text || '{}';
    const clean = text.replace(/```json|```/g, '').trim();
    const parsed = JSON.parse(clean);

    return res.status(200).json({
      ids: parsed.ids || [],
      message: parsed.message || '',
    });
  } catch (err) {
    console.error('Search API error:', err);
    return res.status(500).json({ error: err.message });
  }
}
