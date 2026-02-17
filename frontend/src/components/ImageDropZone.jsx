import { useRef, useState, useEffect, useCallback } from 'react';
import { Box, Typography, IconButton } from '@mui/material';
import { Close, Image as ImageIcon } from '@mui/icons-material';

const ACCEPT = '.png,.jpg,.jpeg,.gif,.webp';
const ACCEPT_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];

export default function ImageDropZone({ label, imageUrl, onImageSelect, onImageRemove }) {
  const fileInputRef = useRef(null);
  const zoneRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [dragging, setDragging] = useState(false);

  // Preview de archivo local seleccionado
  useEffect(() => {
    return () => { if (preview) URL.revokeObjectURL(preview); };
  }, [preview]);

  const handleFile = useCallback((file) => {
    if (!file || !ACCEPT_TYPES.includes(file.type)) return;
    if (preview) URL.revokeObjectURL(preview);
    setPreview(URL.createObjectURL(file));
    onImageSelect(file);
  }, [onImageSelect, preview]);

  const handleRemove = (e) => {
    e.stopPropagation();
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    onImageRemove();
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Paste handler
  useEffect(() => {
    const zone = zoneRef.current;
    if (!zone) return;
    const handlePaste = (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (ACCEPT_TYPES.includes(item.type)) {
          e.preventDefault();
          handleFile(item.getAsFile());
          return;
        }
      }
    };
    zone.addEventListener('paste', handlePaste);
    return () => zone.removeEventListener('paste', handlePaste);
  }, [handleFile]);

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const onDragOver = (e) => { e.preventDefault(); setDragging(true); };
  const onDragLeave = () => setDragging(false);

  const displayUrl = preview || imageUrl;

  return (
    <Box
      ref={zoneRef}
      tabIndex={0}
      onClick={() => fileInputRef.current?.click()}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      sx={{
        border: '2px dashed',
        borderColor: dragging ? 'primary.main' : 'grey.400',
        borderRadius: 1,
        p: 1.5,
        textAlign: 'center',
        cursor: 'pointer',
        bgcolor: dragging ? 'action.hover' : 'background.paper',
        position: 'relative',
        minHeight: 100,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        '&:focus': { borderColor: 'primary.main', outline: 'none' },
      }}
    >
      <input
        type="file"
        accept={ACCEPT}
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {displayUrl ? (
        <>
          <Box
            component="img"
            src={displayUrl}
            alt={label}
            sx={{ maxHeight: 120, maxWidth: '100%', objectFit: 'contain', borderRadius: 0.5 }}
          />
          <IconButton
            size="small"
            onClick={handleRemove}
            sx={{ position: 'absolute', top: 4, right: 4, bgcolor: 'rgba(0,0,0,0.5)', color: 'white', '&:hover': { bgcolor: 'rgba(0,0,0,0.7)' } }}
          >
            <Close fontSize="small" />
          </IconButton>
        </>
      ) : (
        <>
          <ImageIcon sx={{ fontSize: 32, color: 'grey.500', mb: 0.5 }} />
          <Typography variant="caption" color="text.secondary">{label}</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
            Pegar, arrastrar o click
          </Typography>
        </>
      )}
    </Box>
  );
}
