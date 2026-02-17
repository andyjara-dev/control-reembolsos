import { useRef, useState, useEffect, useCallback } from 'react';
import { Box, Typography, IconButton, Dialog, DialogContent } from '@mui/material';
import { Close, Image as ImageIcon, ArrowBack, ArrowForward } from '@mui/icons-material';
import api from '../api';

const ACCEPT = '.png,.jpg,.jpeg,.gif,.webp';
const ACCEPT_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];

export default function MultiImageDropZone({ label, existingImages = [], newFiles = [], onFilesAdd, onNewFileRemove, onExistingRemove }) {
  const fileInputRef = useRef(null);
  const zoneRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [previews, setPreviews] = useState([]);
  const [existingBlobUrls, setExistingBlobUrls] = useState({});
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerIndex, setViewerIndex] = useState(0);

  useEffect(() => {
    const urls = newFiles.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [newFiles]);

  useEffect(() => {
    let cancelled = false;
    const newUrls = {};
    const load = async () => {
      for (const img of existingImages) {
        try {
          const res = await api.get(img.url, { responseType: 'blob' });
          if (cancelled) return;
          newUrls[img.id] = URL.createObjectURL(res.data);
        } catch { /* ignore */ }
      }
      if (!cancelled) {
        setExistingBlobUrls(newUrls);
      }
    };
    load();
    return () => {
      cancelled = true;
      Object.values(newUrls).forEach((u) => URL.revokeObjectURL(u));
    };
  }, [existingImages]);

  const handleFiles = useCallback((fileList) => {
    const valid = Array.from(fileList).filter((f) => ACCEPT_TYPES.includes(f.type));
    if (valid.length > 0) onFilesAdd(valid);
  }, [onFilesAdd]);

  useEffect(() => {
    const zone = zoneRef.current;
    if (!zone) return;
    const handlePaste = (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      const files = [];
      for (const item of items) {
        if (ACCEPT_TYPES.includes(item.type)) {
          files.push(item.getAsFile());
        }
      }
      if (files.length > 0) {
        e.preventDefault();
        onFilesAdd(files);
      }
    };
    zone.addEventListener('paste', handlePaste);
    return () => zone.removeEventListener('paste', handlePaste);
  }, [onFilesAdd]);

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e) => { e.preventDefault(); setDragging(true); };
  const onDragLeave = () => setDragging(false);

  const hasImages = existingImages.length > 0 || newFiles.length > 0;

  // Build ordered list of all viewable image URLs
  const allViewerUrls = [
    ...existingImages.map((img) => existingBlobUrls[img.id]).filter(Boolean),
    ...previews.filter(Boolean),
  ];

  const openViewer = (index, e) => {
    e.stopPropagation();
    setViewerIndex(index);
    setViewerOpen(true);
  };

  return (
    <Box
      ref={zoneRef}
      tabIndex={0}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      sx={{
        border: '2px dashed',
        borderColor: dragging ? 'primary.main' : 'grey.400',
        borderRadius: 1,
        p: 1.5,
        cursor: 'pointer',
        bgcolor: dragging ? 'action.hover' : 'background.paper',
        minHeight: 100,
        '&:focus': { borderColor: 'primary.main', outline: 'none' },
      }}
    >
      <input
        type="file"
        accept={ACCEPT}
        multiple
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={(e) => { handleFiles(e.target.files); e.target.value = ''; }}
      />

      {hasImages && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
          {existingImages.map((img, idx) => (
            <Box key={img.id} sx={{ position: 'relative', width: 80, height: 80 }}>
              <Box
                component="img"
                src={existingBlobUrls[img.id] || ''}
                onClick={(e) => openViewer(idx, e)}
                sx={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 0.5, cursor: 'pointer', '&:hover': { opacity: 0.8 } }}
              />
              <IconButton
                size="small"
                onClick={(e) => { e.stopPropagation(); onExistingRemove(img.id); }}
                sx={{ position: 'absolute', top: -8, right: -8, bgcolor: 'rgba(0,0,0,0.6)', color: 'white', p: 0.3, '&:hover': { bgcolor: 'rgba(0,0,0,0.8)' } }}
              >
                <Close sx={{ fontSize: 14 }} />
              </IconButton>
            </Box>
          ))}
          {newFiles.map((_, idx) => (
            <Box key={`new-${idx}`} sx={{ position: 'relative', width: 80, height: 80 }}>
              <Box
                component="img"
                src={previews[idx]}
                onClick={(e) => openViewer(existingImages.length + idx, e)}
                sx={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 0.5, cursor: 'pointer', '&:hover': { opacity: 0.8 } }}
              />
              <IconButton
                size="small"
                onClick={(e) => { e.stopPropagation(); onNewFileRemove(idx); }}
                sx={{ position: 'absolute', top: -8, right: -8, bgcolor: 'rgba(0,0,0,0.6)', color: 'white', p: 0.3, '&:hover': { bgcolor: 'rgba(0,0,0,0.8)' } }}
              >
                <Close sx={{ fontSize: 14 }} />
              </IconButton>
            </Box>
          ))}
        </Box>
      )}

      <Box
        onClick={() => fileInputRef.current?.click()}
        sx={{ textAlign: 'center', py: hasImages ? 0.5 : 2 }}
      >
        <ImageIcon sx={{ fontSize: 24, color: 'grey.500', mb: 0.5 }} />
        <Typography variant="caption" display="block" color="text.secondary">{label}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
          Pegar, arrastrar o click (múltiples)
        </Typography>
      </Box>

      <Dialog
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
        maxWidth="lg"
        onClick={(e) => e.stopPropagation()}
        PaperProps={{ sx: { bgcolor: 'rgba(0,0,0,0.9)', boxShadow: 'none', position: 'relative' } }}
      >
        <IconButton
          onClick={() => setViewerOpen(false)}
          sx={{ position: 'absolute', top: 8, right: 8, color: 'white', zIndex: 1 }}
        >
          <Close />
        </IconButton>
        <DialogContent sx={{ p: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300, minWidth: 300 }}>
          {allViewerUrls.length > 1 && (
            <IconButton
              onClick={() => setViewerIndex((i) => (i - 1 + allViewerUrls.length) % allViewerUrls.length)}
              sx={{ color: 'white', position: 'absolute', left: 8 }}
            >
              <ArrowBack />
            </IconButton>
          )}
          {allViewerUrls[viewerIndex] && (
            <Box
              component="img"
              src={allViewerUrls[viewerIndex]}
              sx={{ maxWidth: '80vw', maxHeight: '80vh', objectFit: 'contain' }}
            />
          )}
          {allViewerUrls.length > 1 && (
            <IconButton
              onClick={() => setViewerIndex((i) => (i + 1) % allViewerUrls.length)}
              sx={{ color: 'white', position: 'absolute', right: 8 }}
            >
              <ArrowForward />
            </IconButton>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}
