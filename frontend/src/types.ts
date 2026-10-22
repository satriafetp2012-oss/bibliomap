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

// --- workspace ----------------------------------------------------------

export interface FilterSpec {
  year_from: number | null;
  year_to: number | null;
  document_types: DocumentType[];
  languages: string[];
  min_cited_by: number | null;
  require_abstract: boolean;
}

export interface Workspace {
  id: string;
  name: string;
  created_at: string;
  version: number;
  filters: FilterSpec;
}

export interface ImportInfo {
  id: number;
  label: string;
  source_format: SourceFormat;
  origin: string | null;
  record_count: number;
  warnings: ParseWarning[];
  created_at: string;
}

export interface WorkspaceSummary {
  workspace: Workspace;
  imports: ImportInfo[];
  counts: {
    identified: number;
    unique: number;
    duplicates_removed: number;
    pending_reviews: number;
    kept: number;
    excluded: number;
  };
}

export interface RecordView {
  id: number;
  import_label: string;
  source_format: SourceFormat;
  title: string;
  authors: string[];
  author_count: number;
  year: number | null;
  source_title: string | null;
  document_type: DocumentType;
  doi: string | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  abstract: string | null;
}

export interface PendingPair {
  a: RecordView;
  b: RecordView;
  title_similarity: number;
  reasons: string[];
}

export interface PendingPage {
  total: number;
  items: PendingPair[];
}

export type ExclusionReason = "year" | "document_type" | "language" | "citations" | "no_abstract";

export interface SourceRef {
  record_id: number;
  import_id: number;
  source_format: SourceFormat;
  source_id: string | null;
}

export interface RecordRow {
  merged: { id: number; record: BibRecord; sources: SourceRef[] };
  exclusion_reason: ExclusionReason | null;
}

export interface RecordPage {
  total: number;
  items: RecordRow[];
}

export interface PrismaFlow {
  identified: number;
  identified_by_source: { label: string; count: number }[];
  duplicates_removed: number;
  automation_ineligible: number;
  automation_ineligible_by_reason: Partial<Record<ExclusionReason, number>>;
  other_removed: number;
  screened: number;
  screening_excluded: number | null;
  sought_for_retrieval: number | null;
  not_retrieved: number | null;
  assessed_for_eligibility: number | null;
  reports_excluded: number | null;
  included: number | null;
  pending_duplicate_reviews: number;
}
