export type Article = {
  id: number;
  title: string;
  url: string;
  source?: string | null;
  published_at?: string | null;
  snippet?: string | null;
  content_text?: string | null;
  discovered_at?: string | null;
  is_new?: boolean | null;
};

export type Summary = {
  summary_text: string;
  generated_at: string;
};

export type Company = {
  id: number;
  name: string;
  description?: string | null;
  sector?: string | null;
  website?: string | null;
  logo_url?: string | null;
  summary?: Summary | null;
  articles: Article[];
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

function getBaseUrl(): string {
  if (!API_BASE_URL) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  return API_BASE_URL.replace(/\/$/, "");
}

export async function fetchCompanies(): Promise<Company[]> {
  const res = await fetch(`${getBaseUrl()}/companies`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch companies: ${res.status}`);
  }
  return res.json();
}

export async function refreshCompany(companyId: number): Promise<void> {
  const res = await fetch(`${getBaseUrl()}/refresh/${companyId}`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to refresh company: ${res.status}`);
  }
}

export async function scrapePortfolio(): Promise<void> {
  const res = await fetch(`${getBaseUrl()}/scrape-portfolio`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to scrape portfolio: ${res.status}`);
  }
}

export async function refreshAll(): Promise<void> {
  const res = await fetch(`${getBaseUrl()}/refresh-all`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to refresh all: ${res.status}`);
  }
}
