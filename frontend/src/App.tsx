import { useEffect, useMemo, useState } from "react";
import { apiUrl } from "./apiBase";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type PositionRow = { ticker: string; weight: string };

type TickerMetric = { ticker: string; weight: number; beta: number };

type ChartPayload = {
  dates: string[];
  portfolio_nav: number[];
  index_nav: number[];
};

type AnalyzeResult = {
  mode: string;
  portfolio_beta: number;
  per_ticker: TickerMetric[];
  var_1d: number;
  es_1d: number;
  alpha: number;
  confidence_level: number;
  market_index: string;
  warnings: string[];
  chart?: ChartPayload | null;
};

type NewsArticle = {
  title: string;
  link: string;
  published_at: string;
  source?: string | null;
};

type NewsForTicker = {
  ticker: string;
  provider: string;
  articles: NewsArticle[];
  error?: string | null;
};

type NewsBundle = {
  days: number;
  by_ticker: NewsForTicker[];
  warnings: string[];
};

const NEWS_DAYS = 10;

export default function App() {
  const [health, setHealth] = useState<string>("…");
  const [positions, setPositions] = useState<PositionRow[]>([
    { ticker: "SBER", weight: "0.4" },
    { ticker: "GAZP", weight: "0.6" },
  ]);
  const [tradingDays, setTradingDays] = useState("252");
  const [alpha, setAlpha] = useState("0.05");
  const [marketIndex, setMarketIndex] = useState("IMOEX");
  const [useMock, setUseMock] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [news, setNews] = useState<NewsBundle | null>(null);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState<string | null>(null);

  const loadNews = (tickers: string[]) => {
    const uniq = [...new Set(tickers.map((t) => t.trim().toUpperCase()).filter(Boolean))];
    if (uniq.length === 0) {
      setNews(null);
      setNewsError("Нет тикеров для новостей");
      return;
    }
    setNewsLoading(true);
    setNewsError(null);
    const q = encodeURIComponent(uniq.join(","));
    fetch(apiUrl(`/api/news?tickers=${q}&days=${NEWS_DAYS}`))
      .then(async (r) => {
        if (!r.ok) {
          const t = await r.text();
          throw new Error(t || r.statusText);
        }
        return r.json() as Promise<NewsBundle>;
      })
      .then(setNews)
      .catch((e: Error) => {
        setNews(null);
        setNewsError(e.message);
      })
      .finally(() => setNewsLoading(false));
  };

  const loadNewsFromTable = () => {
    const tickers = positions.map((r) => r.ticker.trim().toUpperCase()).filter(Boolean);
    loadNews(tickers);
  };

  useEffect(() => {
    fetch(apiUrl("/api/health"))
      .then((r) => r.json())
      .then((d: { status?: string }) => setHealth(d.status ?? JSON.stringify(d)))
      .catch(() => setHealth("ошибка сети"));
  }, []);

  const chartData = useMemo(() => {
    if (!result?.chart) return [];
    const { dates, portfolio_nav, index_nav } = result.chart;
    return dates.map((d, i) => ({
      date: d,
      portfolio: portfolio_nav[i],
      index: index_nav[i],
    }));
  }, [result]);

  useEffect(() => {
    if (!result?.per_ticker?.length) return;
    loadNews(result.per_ticker.map((p) => p.ticker));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- только после нового результата расчёта
  }, [result]);

  const runAnalyze = () => {
    setError(null);
    setNews(null);
    setNewsError(null);
    setLoading(true);
    const parsed: { ticker: string; weight: number }[] = [];
    for (const row of positions) {
      const t = row.ticker.trim().toUpperCase();
      const w = Number(row.weight.replace(",", "."));
      if (!t) continue;
      if (!Number.isFinite(w) || w <= 0) {
        setError(`Некорректный вес для ${t || "пустого тикера"}`);
        setLoading(false);
        return;
      }
      parsed.push({ ticker: t, weight: w });
    }
    if (parsed.length === 0) {
      setError("Добавьте хотя бы одну позицию с тикером и весом");
      setLoading(false);
      return;
    }
    const td = Number(tradingDays);
    const al = Number(alpha.replace(",", "."));
    if (!Number.isFinite(td) || td < 50) {
      setError("trading_days: число ≥ 50");
      setLoading(false);
      return;
    }
    if (!Number.isFinite(al) || al <= 0 || al >= 0.5) {
      setError("alpha: число между 0 и 0.5");
      setLoading(false);
      return;
    }

    fetch(apiUrl("/api/portfolio/analyze"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        positions: parsed.map((p) => ({ ticker: p.ticker, weight: p.weight })),
        trading_days: Math.round(td),
        alpha: al,
        market_index: marketIndex.trim() || "IMOEX",
        use_mock: useMock,
      }),
    })
      .then(async (r) => {
        if (!r.ok) {
          let msg = r.statusText;
          try {
            const j = await r.json();
            if (j?.detail?.message) msg = j.detail.message;
            else msg = JSON.stringify(j);
          } catch {
            try {
              msg = await r.text();
            } catch {
              /* noop */
            }
          }
          throw new Error(msg);
        }
        return r.json() as Promise<AnalyzeResult>;
      })
      .then(setResult)
      .catch((e: Error) => {
        setResult(null);
        setError(e.message);
      })
      .finally(() => setLoading(false));
  };

  const addRow = () => setPositions((p) => [...p, { ticker: "", weight: "0.1" }]);
  const removeRow = (i: number) => setPositions((p) => p.filter((_, j) => j !== i));
  const updateRow = (i: number, field: keyof PositionRow, value: string) => {
    setPositions((p) => p.map((row, j) => (j === i ? { ...row, [field]: value } : row)));
  };

  return (
    <main className="page">
      <h1>Портфель: CAPM, VaR, ES</h1>
      <p className="muted">
        Данные: MOEX ISS (акции TQBR, индекс). Секреты — только в <code>.env</code>. Учебный проект.
      </p>
      <p>
        API health: <strong>{health}</strong>
      </p>

      <section className="section">
        <h2>Портфель</h2>
        <table className="tbl">
          <thead>
            <tr>
              <th>Тикер</th>
              <th>Вес</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {positions.map((row, i) => (
              <tr key={i}>
                <td>
                  <input
                    className="inp"
                    value={row.ticker}
                    onChange={(e) => updateRow(i, "ticker", e.target.value)}
                    placeholder="SBER"
                  />
                </td>
                <td>
                  <input
                    className="inp inp-narrow"
                    value={row.weight}
                    onChange={(e) => updateRow(i, "weight", e.target.value)}
                  />
                </td>
                <td>
                  <button type="button" className="btn-sm" onClick={() => removeRow(i)}>
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="row">
          <button type="button" className="btn-secondary" onClick={addRow}>
            + Позиция
          </button>
        </div>

        <div className="grid2">
          <label className="lbl">
            Окно, торг. дней
            <input
              className="inp"
              value={tradingDays}
              onChange={(e) => setTradingDays(e.target.value)}
            />
          </label>
          <label className="lbl">
            Alpha (хвост VaR/ES)
            <input className="inp" value={alpha} onChange={(e) => setAlpha(e.target.value)} />
          </label>
          <label className="lbl">
            Индекс рынка
            <input
              className="inp"
              value={marketIndex}
              onChange={(e) => setMarketIndex(e.target.value)}
            />
          </label>
          <label className="lbl chk">
            <input
              type="checkbox"
              checked={useMock}
              onChange={(e) => setUseMock(e.target.checked)}
            />
            Mock (без MOEX)
          </label>
        </div>

        <div className="row gap">
          <button type="button" className="btn" onClick={runAnalyze} disabled={loading}>
            {loading ? "Считаем…" : "Рассчитать"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={loadNewsFromTable}
            disabled={newsLoading}
          >
            {newsLoading ? "Новости…" : `Новости (${NEWS_DAYS} дн.) по таблице`}
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {newsError ? <p className="error">{newsError}</p> : null}
      </section>

      {result ? (
        <section className="section">
          <h2>Результат ({result.mode})</h2>
          <div className="metrics">
            <div className="metric">
              <span className="metric-lbl">Портфельная β</span>
              <span className="metric-val">{result.portfolio_beta}</span>
            </div>
            <div className="metric">
              <span className="metric-lbl">VaR 1д (доля потери)</span>
              <span className="metric-val">{result.var_1d}</span>
            </div>
            <div className="metric">
              <span className="metric-lbl">ES 1д (пробой)</span>
              <span className="metric-val">{result.es_1d}</span>
            </div>
            <div className="metric">
              <span className="metric-lbl">Доверие</span>
              <span className="metric-val">{(result.confidence_level * 100).toFixed(1)}%</span>
            </div>
            <div className="metric wide">
              <span className="metric-lbl">Индекс</span>
              <span className="metric-val">{result.market_index}</span>
            </div>
          </div>

          <h3>По тикерам</h3>
          <table className="tbl">
            <thead>
              <tr>
                <th>Тикер</th>
                <th>Вес</th>
                <th>β</th>
              </tr>
            </thead>
            <tbody>
              {result.per_ticker.map((p) => (
                <tr key={p.ticker}>
                  <td>{p.ticker}</td>
                  <td>{p.weight}</td>
                  <td>{p.beta}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {result.warnings?.length ? (
            <ul className="warn-list">
              {result.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : null}

          {chartData.length > 0 ? (
            <>
              <h3>График (нормированный NAV)</h3>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={24} />
                    <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} width={48} />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="portfolio"
                      name="Портфель"
                      stroke="#1d4ed8"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="index"
                      name={result.market_index}
                      stroke="#64748b"
                      strokeWidth={2}
                      dot={false}
                      strokeDasharray="6 4"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      {news && news.by_ticker.length > 0 ? (
        <section className="section">
          <h2>Новости за {news.days} дн.</h2>
          {news.warnings?.length ? (
            <ul className="warn-list">
              {news.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : null}
          {news.by_ticker.map((block) => (
            <div key={block.ticker} className="news-block">
              <h3 className="news-ticker">
                {block.ticker}{" "}
                <span className="muted news-provider">({block.provider})</span>
              </h3>
              {block.error ? (
                <p className="error">{block.error}</p>
              ) : block.articles.length === 0 ? (
                <p className="muted">За выбранный период заголовков не найдено.</p>
              ) : (
                <ul className="news-list">
                  {block.articles.map((a, i) => (
                    <li key={`${a.link}-${i}`} className="news-item">
                      <a href={a.link} target="_blank" rel="noopener noreferrer">
                        {a.title}
                      </a>
                      <div className="news-meta">
                        {new Date(a.published_at).toLocaleString("ru-RU", {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                        {a.source ? ` · ${a.source}` : ""}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </section>
      ) : null}
    </main>
  );
}
