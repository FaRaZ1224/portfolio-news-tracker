"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { Company } from "@/lib/api";
import { fetchCompanies, refreshAll, refreshCompany } from "@/lib/api";

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
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000);
      const data = await fetchCompanies(controller.signal);
      clearTimeout(timeout);
      setCompanies(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load";
      setError(
        msg.includes("aborted")
          ? "Backend is taking too long to respond (may be waking up). Wait a bit and press Retry."
          : msg
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const totalArticles = useMemo(() => companies.reduce((acc, c) => acc + (c.articles?.length || 0), 0), [companies]);

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
              onClick={onRefreshAll}
              disabled={busyGlobal}
              className="h-10 rounded-md bg-zinc-900 px-4 text-sm font-medium text-white shadow-sm hover:bg-zinc-800 disabled:opacity-60"
            >
              {busyGlobal ? "Working..." : "Refresh All"}
            </button>
          </div>
        </div>

        {error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">{error}</div>
              <button
                onClick={() => void load()}
                className="h-9 shrink-0 rounded-md bg-white px-3 text-xs font-semibold text-zinc-900 shadow-sm ring-1 ring-zinc-200 hover:bg-zinc-50"
              >
                Retry
              </button>
            </div>
          </div>
        ) : null}

        {loading ? (
          <div className="mt-10 text-sm text-zinc-600">Loading…</div>
        ) : companies.length === 0 ? (
          <div className="mt-10 rounded-lg border border-dashed border-zinc-200 bg-white p-10">
            <div className="text-base font-medium">No companies yet</div>
            <div className="mt-2 text-sm text-zinc-600">Import companies into the database to begin tracking news.</div>
          </div>
        ) : (
          <div className="mt-8 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-zinc-200">
            <table className="w-full border-collapse">
              <thead className="bg-zinc-50">
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-zinc-600">
                  <th className="w-12 px-4 py-3"> </th>
                  <th className="px-4 py-3">Company</th>
                  <th className="hidden px-4 py-3 sm:table-cell">Tags</th>
                  <th className="hidden px-4 py-3 md:table-cell">Summary</th>
                  <th className="w-40 px-4 py-3 text-right"> </th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => {
                  const isBusy = busyCompanyId === company.id || busyGlobal;
                  return (
                    <tbody key={company.id} className="[&>tr]:w-full">
                      <tr className="border-t border-zinc-200 align-top">
                        <td className="px-4 py-4">
                          <div className="h-10 w-10 overflow-hidden rounded-lg bg-white ring-1 ring-zinc-200">
                            {company.logo_url ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={company.logo_url} alt={company.name} className="h-full w-full object-contain p-1" />
                            ) : (
                              <div className="h-full w-full bg-zinc-100" />
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-zinc-950">{company.name}</div>
                            {company.website ? (
                              <a
                                href={company.website}
                                target="_blank"
                                rel="noreferrer"
                                className="mt-1 inline-block text-xs font-medium text-zinc-600 underline decoration-zinc-300 underline-offset-4 hover:text-zinc-900"
                              >
                                Website
                              </a>
                            ) : null}
                          </div>
                        </td>
                        <td className="hidden px-4 py-4 text-xs text-zinc-600 sm:table-cell">{company.sector || "—"}</td>
                        <td className="hidden px-4 py-4 md:table-cell">
                          <div className="line-clamp-2 text-sm leading-6 text-zinc-900">
                            {company.summary?.summary_text || "No summary yet. Click Refresh."}
                          </div>
                        </td>
                        <td className="px-4 py-4 text-right">
                          <button
                            onClick={() => onRefreshCompany(company.id)}
                            disabled={isBusy}
                            className="h-9 rounded-md bg-zinc-900 px-3 text-xs font-semibold text-white hover:bg-zinc-800 disabled:opacity-60"
                          >
                            {isBusy ? "Refreshing…" : "Refresh"}
                          </button>
                        </td>
                      </tr>

                      <tr className="border-t border-zinc-200 bg-white">
                        <td colSpan={5} className="px-4 py-4">
                          <div className="text-xs font-semibold text-zinc-700">News</div>
                          {company.articles?.length ? (
                            <div className="mt-3 divide-y divide-zinc-200 rounded-lg border border-zinc-200">
                              {company.articles.slice(0, 8).map((a) => (
                                <a
                                  key={a.id}
                                  href={a.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="block bg-white px-3 py-3 hover:bg-zinc-50"
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
                            <div className="mt-2 text-sm text-zinc-500">No recent articles found yet.</div>
                          )}
                        </td>
                      </tr>
                    </tbody>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-10 text-xs text-zinc-500">
          Configure <span className="font-medium text-zinc-700">NEXT_PUBLIC_API_BASE_URL</span> in Netlify to point to
          your backend base URL.
        </div>
      </div>
    </div>
  );
}
