"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { Company } from "@/lib/api";
import { fetchCompanies, refreshAll, refreshCompany, scrapePortfolio } from "@/lib/api";

function formatDate(value?: string | null): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function DashboardClient() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyCompanyId, setBusyCompanyId] = useState<number | null>(null);
  const [busyGlobal, setBusyGlobal] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await fetchCompanies();
      setCompanies(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const totalArticles = useMemo(() => companies.reduce((acc, c) => acc + (c.articles?.length || 0), 0), [companies]);

  const onScrape = useCallback(async () => {
    setBusyGlobal(true);
    setError(null);
    try {
      await scrapePortfolio();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to scrape");
    } finally {
      setBusyGlobal(false);
    }
  }, [load]);

  const onRefreshAll = useCallback(async () => {
    setBusyGlobal(true);
    setError(null);
    try {
      await refreshAll();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh all");
    } finally {
      setBusyGlobal(false);
    }
  }, [load]);

  const onRefreshCompany = useCallback(
    async (companyId: number) => {
      setBusyCompanyId(companyId);
      setError(null);
      try {
        await refreshCompany(companyId);
        await load();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to refresh");
      } finally {
        setBusyCompanyId(null);
      }
    },
    [load]
  );

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-950">
      <div className="mx-auto w-full max-w-6xl px-6 py-10">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">Initialized Portfolio News Tracker</h1>
            <p className="text-sm text-zinc-600">
              Companies: <span className="font-medium text-zinc-900">{companies.length}</span> · Articles:{" "}
              <span className="font-medium text-zinc-900">{totalArticles}</span>
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              onClick={onScrape}
              disabled={busyGlobal}
              className="h-10 rounded-md bg-white px-4 text-sm font-medium text-zinc-900 shadow-sm ring-1 ring-zinc-200 hover:bg-zinc-50 disabled:opacity-60"
            >
              {busyGlobal ? "Working..." : "Scrape Portfolio"}
            </button>
            <button
              onClick={onRefreshAll}
              disabled={busyGlobal}
              className="h-10 rounded-md bg-zinc-900 px-4 text-sm font-medium text-white shadow-sm hover:bg-zinc-800 disabled:opacity-60"
            >
              {busyGlobal ? "Working..." : "Refresh All"}
            </button>
          </div>
        </div>

        {error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
        ) : null}

        {loading ? (
          <div className="mt-10 text-sm text-zinc-600">Loading…</div>
        ) : companies.length === 0 ? (
          <div className="mt-10 rounded-lg border border-dashed border-zinc-200 bg-white p-10">
            <div className="text-base font-medium">No companies yet</div>
            <div className="mt-2 text-sm text-zinc-600">Click “Scrape Portfolio” to import Initialized companies.</div>
          </div>
        ) : (
          <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {companies.map((company) => {
              const isBusy = busyCompanyId === company.id || busyGlobal;
              return (
                <div key={company.id} className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-zinc-200">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="truncate text-base font-semibold text-zinc-950">{company.name}</div>
                      {company.sector ? <div className="mt-1 text-xs text-zinc-500">{company.sector}</div> : null}
                    </div>
                    <button
                      onClick={() => onRefreshCompany(company.id)}
                      disabled={isBusy}
                      className="h-9 shrink-0 rounded-md bg-zinc-900 px-3 text-xs font-semibold text-white hover:bg-zinc-800 disabled:opacity-60"
                    >
                      {isBusy ? "Refreshing…" : "Refresh"}
                    </button>
                  </div>

                  {company.description ? (
                    <p className="mt-3 line-clamp-3 text-sm leading-6 text-zinc-600">{company.description}</p>
                  ) : (
                    <p className="mt-3 text-sm text-zinc-500">No description available.</p>
                  )}

                  <div className="mt-4 rounded-lg bg-zinc-50 p-4 ring-1 ring-zinc-200">
                    <div className="text-xs font-semibold text-zinc-700">Summary</div>
                    <div className="mt-2 text-sm leading-6 text-zinc-900">
                      {company.summary?.summary_text || "No summary yet. Click Refresh."}
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-semibold text-zinc-700">Recent Articles</div>
                      {company.website ? (
                        <a
                          href={company.website}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-medium text-zinc-700 underline decoration-zinc-300 underline-offset-4 hover:text-zinc-900"
                        >
                          Website
                        </a>
                      ) : null}
                    </div>

                    {company.articles?.length ? (
                      <div className="mt-3 space-y-3">
                        {company.articles.slice(0, 5).map((a) => (
                          <a
                            key={a.id}
                            href={a.url}
                            target="_blank"
                            rel="noreferrer"
                            className="block rounded-lg border border-zinc-200 bg-white p-3 hover:bg-zinc-50"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="line-clamp-2 text-sm font-medium text-zinc-950">{a.title}</div>
                                <div className="mt-1 text-xs text-zinc-600">
                                  {(a.source || "Unknown source") + (a.published_at ? ` · ${formatDate(a.published_at)}` : "")}
                                </div>
                              </div>
                              {a.is_new ? (
                                <div className="shrink-0 rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-bold text-emerald-800 ring-1 ring-emerald-200">
                                  NEW
                                </div>
                              ) : null}
                            </div>
                          </a>
                        ))}
                      </div>
                    ) : (
                      <div className="mt-3 text-sm text-zinc-500">No recent articles found yet.</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-10 text-xs text-zinc-500">
          Configure <span className="font-medium text-zinc-700">NEXT_PUBLIC_API_BASE_URL</span> in Netlify to point to
          your Railway backend.
        </div>
      </div>
    </div>
  );
}
