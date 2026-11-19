export const CONTRACT_TYPES = [
    'Employment Agreement',
    'Job Offer',
    'Severance Agreement',
    'Service/Vendor Contract',
    'Lease',
    'General',
];
export function supportsHrReport(type) {
    return type === 'Employment Agreement' || type === 'Job Offer' || type === 'Severance Agreement';
}
