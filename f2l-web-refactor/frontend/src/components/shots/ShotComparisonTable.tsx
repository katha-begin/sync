import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Typography,
  Box,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Warning as WarningIcon,
  Download as DownloadIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { ShotComparison, COMPARISON_STATUS_LABELS, COMPARISON_STATUS_COLORS } from '@/types/shot';
import { formatBytes } from '@/utils/formatters';

interface ShotComparisonTableProps {
  comparisons: ShotComparison[];
}

const ShotComparisonTable: React.FC<ShotComparisonTableProps> = ({ comparisons }) => {
  const getStatusIcon = (status: ShotComparison['status']) => {
    switch (status) {
      case 'up_to_date':
        return <CheckIcon fontSize="small" />;
      case 'update_available':
        return <WarningIcon fontSize="small" />;
      case 'new_download':
        return <DownloadIcon fontSize="small" />;
      case 'ftp_missing':
      case 'error':
        return <ErrorIcon fontSize="small" />;
      default:
        return null;
    }
  };

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Episode</TableCell>
            <TableCell>Sequence</TableCell>
            <TableCell>Shot</TableCell>
            <TableCell>Department</TableCell>
            <TableCell>FTP Version</TableCell>
            <TableCell>Local Version</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Files</TableCell>
            <TableCell align="right">Size</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {comparisons.map((comp, index) => (
            <TableRow
              key={`${comp.episode}-${comp.sequence}-${comp.shot}-${comp.department}-${index}`}
              sx={{
                backgroundColor: comp.needs_update ? 'rgba(255, 152, 0, 0.05)' : 'inherit',
              }}
            >
              <TableCell>{comp.episode}</TableCell>
              <TableCell>{comp.sequence}</TableCell>
              <TableCell>{comp.shot}</TableCell>
              <TableCell>
                <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                  {comp.department}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2" fontFamily="monospace">
                  {comp.ftp_version || '-'}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2" fontFamily="monospace">
                  {comp.local_version || '-'}
                </Typography>
              </TableCell>
              <TableCell>
                <Chip
                  icon={getStatusIcon(comp.status) || undefined}
                  label={COMPARISON_STATUS_LABELS[comp.status]}
                  size="small"
                  sx={{
                    backgroundColor: COMPARISON_STATUS_COLORS[comp.status],
                    color: 'white',
                    fontWeight: 500,
                  }}
                />
              </TableCell>
              <TableCell align="right">
                <Typography variant="body2">{comp.file_count}</Typography>
              </TableCell>
              <TableCell align="right">
                <Typography variant="body2">{formatBytes(comp.total_size)}</Typography>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {comparisons.length === 0 && (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography color="text.secondary">No comparison results</Typography>
        </Box>
      )}

      {/* Summary */}
      {comparisons.length > 0 && (
        <Box sx={{ p: 2, backgroundColor: 'rgba(0, 0, 0, 0.02)' }}>
          <Typography variant="body2" fontWeight="bold">
            Summary:
          </Typography>
          <Typography variant="body2">
            Total: {comparisons.length} items |{' '}
            Needs Update: {comparisons.filter(c => c.needs_update).length} |{' '}
            Up to Date: {comparisons.filter(c => c.status === 'up_to_date').length} |{' '}
            Total Size: {formatBytes(comparisons.reduce((sum, c) => sum + c.total_size, 0))}
          </Typography>
        </Box>
      )}
    </TableContainer>
  );
};

export default ShotComparisonTable;

