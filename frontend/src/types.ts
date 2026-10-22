// Mirrors bibliomap.schema on the backend.

export type SourceFormat =
  | "wos"
  | "scopus"
  | "ris"
  | "pubmed"
  | "bibtex"
  | "openalex"
  | "lens";

export type DocumentType =
  | "article"
  | "review"
  | "conference_paper"
  | "book"
  | "book_chapter"
  | "editorial"
  | "letter"
  | "preprint"
  | "other";

export interface Author {
  name: string;
  full_name: string | null;
  orcid: string | null;
  affiliations: string[];
}

export interface BibRecord {
  source_format: SourceFormat;
  source_id: string | null;
  title: string;
  authors: Author[];
  year: number | null;
  source_title: string | null;
  document_type: DocumentType;
  doi: string | null;
  cited_by: number | null;
}

export interface ParseWarning {
  record_index: number | null;
  message: string;
}

export interface ParseResult {
  source_format: SourceFormat;
  records: BibRecord[];
  warnings: ParseWarning[];
}

export interface ImportPreview {
  filename: string | null;
  record_count: number;
  result: ParseResult;
}

export type SearchScope = "title_and_abstract" | "title" | "fulltext";

export const WORK_TYPES = [
  "article",
  "review",
  "conference-paper",
  "book-chapter",
  "book",
  "preprint",
  "letter",
  "editorial",
] as const;

export type WorkType = (typeof WORK_TYPES)[number];

export interface OpenAlexQuery {
  terms: string;
  scope: SearchScope;
  year_from: number | null;
  year_to: number | null;
  types: WorkType[];
  languages: string[];
  open_access_only: boolean;
  max_results: number;
}

export interface OpenAlexCount {
  count: number;
  query_url: string;
}

export interface OpenAlexImport {
  record_count: number;
  total_available: number;
  truncated: boolean;
  cost_usd: number;
  query_url: string;
  result: ParseResult;
}
