export type Language = 'en' | 'fr';
export type ContractType =
  | 'Employment Agreement'
  | 'Job Offer'
  | 'Severance Agreement'
  | 'Service/Vendor Contract'
  | 'Lease'
  | 'General';

export type SourcePage = {
  sourceId: string;
  documentName: string;
  sourceType: 'CONTRACT' | 'REFERENCE';
  pageNumber: number | null;
  sectionLabel?: string;
  text: string;
};

export type Citation = {
  sourceId: string;
  sourceType: 'CONTRACT' | 'REFERENCE';
  documentName: string;
  pageNumber: number | null;
  sectionLabel?: string;
  verbatimExcerpt: string;
  verified: boolean;
};

export type Finding = {
  id: string;
  title: string;
  category: string;
  explanation: string;
  practicalEffect: string;
  negotiationConsideration: string;
  suggestedWording?: string;
  citations: Citation[];
};

export type ReportObligation = { text: string; citations: Citation[] };
export type HRTopicCode = 'probation' | 'termination_notice' | 'severance' | 'non_compete' | 'non_solicit' | 'ip_assignment' | 'benefits';
export type HRTopicStatus = 'FOUND' | 'NOT_FOUND_IN_SUBMITTED_DOCUMENTS' | 'REQUIRES_JURISDICTIONAL_REVIEW';
export type HRTopicSection = {
  topic: HRTopicCode;
  status: HRTopicStatus;
  analysis: string;
  practicalConsiderations: string;
  citations: Citation[];
};

export type ContractAnalysis = {
  executiveSummary: string;
  executiveSummaryCitations: Citation[];
  findings: Finding[];
  obligations: ReportObligation[];
  terminationOverview: string;
  terminationCitations: Citation[];
  lawyerReport: string;
  lawyerReportCitations: Citation[];
  hrReport?: string;
  hrSections: HRTopicSection[];
  generatedLanguage: Language;
  inferenceSource: 'IN_CLOUD' | 'ON_DEVICE';
};

export type ReviewRecord = {
  id: string;
  userId: string;
  title: string;
  fileName: string;
  contractType: ContractType;
  folderId?: string | null;
  language: Language;
  status: 'analyzed' | 'draft';
  createdAt: number;
  updatedAt: number;
  pages: SourcePage[];
  analysis?: ContractAnalysis;
};

export type ReferenceRecord = {
  id: string;
  userId: string;
  title: string;
  fileName: string;
  folderId?: string | null;
  language: Language;
  createdAt: number;
  pages: SourcePage[];
};

export type FolderRecord = {
  id: string;
  userId: string;
  name: string;
  kind: 'contracts' | 'references' | 'both';
  createdAt: number;
};

export type ParsedDocument = {
  fileName: string;
  pages: Array<{ pageNumber: number | null; sectionLabel?: string; text: string }>;
  notes: string[];
};

export type RedactionResult = {
  pages: Array<{ pageNumber: number | null; sectionLabel?: string; text: string }>;
  tokenMap: Record<string, string>;
  categories: Record<string, number>;
  method: 'GEMINI_NANO' | 'PATTERN_ONLY';
  warnings: string[];
};

export const CONTRACT_TYPES: ContractType[] = [
  'Employment Agreement',
  'Job Offer',
  'Severance Agreement',
  'Service/Vendor Contract',
  'Lease',
  'General',
];

export function supportsHrReport(type: ContractType): boolean {
  return type === 'Employment Agreement' || type === 'Job Offer' || type === 'Severance Agreement';
}
