import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Typography, Table, TableHead, TableRow, TableCell, TableBody, Button, Chip,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField, MenuItem,
  IconButton, Box, Stack, Alert, CircularProgress,
} from '@mui/material';
import { Add, Edit, Delete, Download, PictureAsPdf, Image as ImageIcon } from '@mui/icons-material';
import api from '../api';
import MultiImageDropZone from '../components/MultiImageDropZone';

const estadoColor = { PENDIENTE: 'warning', SOLICITADO: 'info', PAGADO: 'success' };
const TIPOS = ['REEMBOLSO', 'PROVISION'];
const ESTADOS = ['PENDIENTE', 'SOLICITADO', 'PAGADO'];
const MONEDAS = ['USD', 'EUR', 'MXN', 'ARS', 'COP', 'CLP'];
const PAGE_SIZE = 25;

const fechaChile = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago' }).format(new Date());

const emptyPago = {
  fecha_pago: '',
  concepto: '', proveedor: '', monto: '', moneda: 'USD', monto_clp: '',
  tipo: 'REEMBOLSO', estado: 'PENDIENTE',
  fecha_solicitud: '', fecha_reembolso: '', comprobante: '', notas: '',
};

export default function Pagos() {
  const [pagos, setPagos] = useState([]);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [totales, setTotales] = useState({ clp: 0, usd: 0 });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyPago);
  const [editId, setEditId] = useState(null);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({ estado: '', tipo: '', proveedor: '' });
  const [newImagenesCobro, setNewImagenesCobro] = useState([]);
  const [newImagenesReembolso, setNewImagenesReembolso] = useState([]);
  const [existingImagenesCobro, setExistingImagenesCobro] = useState([]);
  const [existingImagenesReembolso, setExistingImagenesReembolso] = useState([]);
  const sentinelRef = useRef(null);
  const pagosRef = useRef([]);

  const buildParams = useCallback((skip = 0) => {
    const params = { skip, limit: PAGE_SIZE };
    if (filters.estado) params.estado = filters.estado;
    if (filters.tipo) params.tipo = filters.tipo;
    if (filters.proveedor) params.proveedor = filters.proveedor;
    return params;
  }, [filters]);

  // Carga inicial (reset) al cambiar filtros
  useEffect(() => {
    let cancelled = false;
    setPagos([]);
    pagosRef.current = [];
    setHasMore(true);
    setTotales({ clp: 0, usd: 0 });

    api.get('/pagos', { params: buildParams(0) }).then((r) => {
      if (cancelled) return;
      const data = r.data;
      pagosRef.current = data.items;
      setPagos(data.items);
      setTotales({ clp: data.total_monto_clp, usd: data.total_monto_usd });
      setHasMore(data.items.length < data.total);
    });

    return () => { cancelled = true; };
  }, [filters, buildParams]);

  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return;
    setIsLoadingMore(true);
    try {
      const r = await api.get('/pagos', { params: buildParams(pagosRef.current.length) });
      const data = r.data;
      const updated = [...pagosRef.current, ...data.items];
      pagosRef.current = updated;
      setPagos(updated);
      setHasMore(updated.length < data.total);
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, hasMore, buildParams]);

  // IntersectionObserver para scroll infinito
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { threshold: 0.1 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadMore]);

  const reload = () => {
    // Fuerza re-ejecución del efecto de carga
    setFilters((f) => ({ ...f }));
  };

  const handleOpen = (pago = null) => {
    if (pago) {
      setEditId(pago.id);
      setForm({
        fecha_pago: pago.fecha_pago || '',
        concepto: pago.concepto || '',
        proveedor: pago.proveedor || '',
        monto: pago.monto || '',
        moneda: pago.moneda || 'USD',
        monto_clp: pago.monto_clp || '',
        tipo: pago.tipo || 'REEMBOLSO',
        estado: pago.estado || 'PENDIENTE',
        fecha_solicitud: pago.fecha_solicitud || '',
        fecha_reembolso: pago.fecha_reembolso || '',
        comprobante: pago.comprobante || '',
        notas: pago.notas || '',
      });
    } else {
      setEditId(null);
      setForm({ ...emptyPago, fecha_pago: fechaChile() });
    }
    setNewImagenesCobro([]);
    setNewImagenesReembolso([]);
    if (pago) {
      setExistingImagenesCobro(
        (pago.imagenes_cobro || []).map((img) => ({ id: img.id, url: `/pagos/${pago.id}/imagen/${img.id}/file` }))
      );
      setExistingImagenesReembolso(
        (pago.imagenes_reembolso || []).map((img) => ({ id: img.id, url: `/pagos/${pago.id}/imagen/${img.id}/file` }))
      );
    } else {
      setExistingImagenesCobro([]);
      setExistingImagenesReembolso([]);
    }
    setError('');
    setOpen(true);
  };

  const handleSave = async () => {
    try {
      const data = { ...form, monto: Number(form.monto) };
      if (form.monto_clp !== '' && form.monto_clp !== null) {
        data.monto_clp = Number(form.monto_clp);
      } else {
        data.monto_clp = null;
      }
      if (!data.fecha_solicitud) data.fecha_solicitud = null;
      if (!data.fecha_reembolso) data.fecha_reembolso = null;
      if (!data.comprobante) data.comprobante = null;
      if (!data.notas) data.notas = null;

      let savedPago;
      if (editId) {
        const res = await api.put(`/pagos/${editId}`, data);
        savedPago = res.data;
      } else {
        const res = await api.post('/pagos', data);
        savedPago = res.data;
      }

      for (const [files, tipo] of [[newImagenesCobro, 'cobro'], [newImagenesReembolso, 'reembolso']]) {
        for (const file of files) {
          const fd = new FormData();
          fd.append('archivo', file);
          await api.post(`/pagos/${savedPago.id}/imagen/${tipo}`, fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
        }
      }

      setOpen(false);
      reload();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al guardar');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar este pago?')) return;
    await api.delete(`/pagos/${id}`);
    reload();
  };

  const handleEstadoChange = async (pago, nuevoEstado) => {
    const updates = { estado: nuevoEstado };
    if (nuevoEstado === 'SOLICITADO' && !pago.fecha_solicitud) {
      updates.fecha_solicitud = fechaChile();
    }
    if (nuevoEstado === 'PAGADO' && !pago.fecha_reembolso) {
      updates.fecha_reembolso = fechaChile();
    }
    await api.put(`/pagos/${pago.id}`, updates);
    reload();
  };

  const handleDownloadArchivo = async (pagoId) => {
    try {
      const res = await api.get(`/pagos/${pagoId}/archivo`, { responseType: 'blob' });
      const disposition = res.headers['content-disposition'];
      let filename = 'archivo';
      if (disposition) {
        const match = disposition.match(/filename="?(.+)"?/);
        if (match) filename = match[1];
      }
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Error al descargar archivo');
    }
  };

  const handleDownloadPdf = async (pagoId) => {
    try {
      const res = await api.get(`/pagos/${pagoId}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `solicitud_${pagoId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Error al generar PDF');
    }
  };

  const handleDescargarReporte = async () => {
    try {
      const params = {};
      if (filters.estado) params.estado = filters.estado;
      if (filters.tipo) params.tipo = filters.tipo;
      if (filters.proveedor) params.proveedor = filters.proveedor;
      const res = await api.get('/pagos/reporte', { params, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'reporte_pagos.pdf');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Error al generar reporte');
    }
  };

  const nextEstado = (estado) => {
    if (estado === 'PENDIENTE') return 'SOLICITADO';
    if (estado === 'SOLICITADO') return 'PAGADO';
    return null;
  };

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">Pagos</Typography>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" startIcon={<PictureAsPdf />} onClick={handleDescargarReporte}>Reporte PDF</Button>
          <Button variant="contained" startIcon={<Add />} onClick={() => handleOpen()}>Nuevo Pago</Button>
        </Stack>
      </Box>

      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <TextField select label="Estado" size="small" value={filters.estado} onChange={(e) => setFilters({ ...filters, estado: e.target.value })} sx={{ minWidth: 140 }}>
          <MenuItem value="">Todos</MenuItem>
          {ESTADOS.map((e) => <MenuItem key={e} value={e}>{e}</MenuItem>)}
        </TextField>
        <TextField select label="Tipo" size="small" value={filters.tipo} onChange={(e) => setFilters({ ...filters, tipo: e.target.value })} sx={{ minWidth: 140 }}>
          <MenuItem value="">Todos</MenuItem>
          {TIPOS.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
        </TextField>
        <TextField label="Proveedor" size="small" value={filters.proveedor} onChange={(e) => setFilters({ ...filters, proveedor: e.target.value })} />
      </Stack>

      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell>Fecha</TableCell>
            <TableCell>Concepto</TableCell>
            <TableCell>Proveedor</TableCell>
            <TableCell align="right">Monto</TableCell>
            <TableCell align="right">Monto CLP</TableCell>
            <TableCell>Tipo</TableCell>
            <TableCell>Estado</TableCell>
            <TableCell>Acciones</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {pagos.map((p) => (
            <TableRow key={p.id}>
              <TableCell>{p.fecha_pago}</TableCell>
              <TableCell>{p.concepto}</TableCell>
              <TableCell>{p.proveedor}</TableCell>
              <TableCell align="right">{Number(p.monto).toFixed(2)} {p.moneda}</TableCell>
              <TableCell align="right">{p.monto_clp ? Number(p.monto_clp).toLocaleString('es-CL', { maximumFractionDigits: 0 }) : '-'}</TableCell>
              <TableCell><Chip label={p.tipo} size="small" variant="outlined" /></TableCell>
              <TableCell>
                <Chip label={p.estado} size="small" color={estadoColor[p.estado]} />
                {nextEstado(p.estado) && (
                  <Button size="small" sx={{ ml: 1 }} onClick={() => handleEstadoChange(p, nextEstado(p.estado))}>
                    → {nextEstado(p.estado)}
                  </Button>
                )}
              </TableCell>
              <TableCell>
                <IconButton size="small" onClick={() => handleOpen(p)}><Edit fontSize="small" /></IconButton>
                <IconButton size="small" color="error" onClick={() => handleDelete(p.id)}><Delete fontSize="small" /></IconButton>
                <IconButton size="small" color="primary" onClick={() => handleDownloadPdf(p.id)} title="Descargar PDF"><PictureAsPdf fontSize="small" /></IconButton>
                {p.archivo_comprobante && (
                  <IconButton size="small" color="primary" onClick={() => handleDownloadArchivo(p.id)} title="Descargar comprobante">
                    <Download fontSize="small" />
                  </IconButton>
                )}
                {((p.imagenes_cobro && p.imagenes_cobro.length > 0) || (p.imagenes_reembolso && p.imagenes_reembolso.length > 0)) && (
                  <IconButton size="small" color="secondary" onClick={() => handleOpen(p)} title={`Imágenes: cobro(${(p.imagenes_cobro || []).length}) reembolso(${(p.imagenes_reembolso || []).length})`}>
                    <ImageIcon fontSize="small" />
                  </IconButton>
                )}
              </TableCell>
            </TableRow>
          ))}
          {pagos.length === 0 && !isLoadingMore && (
            <TableRow><TableCell colSpan={8} align="center">No hay pagos</TableCell></TableRow>
          )}
          {/* Fila de totales */}
          {pagos.length > 0 && (
            <TableRow sx={{ backgroundColor: 'action.hover', fontWeight: 'bold' }}>
              <TableCell colSpan={3} sx={{ fontWeight: 'bold' }}>TOTALES</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                {totales.usd.toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                {totales.clp.toLocaleString('es-CL', { maximumFractionDigits: 0 })} CLP
              </TableCell>
              <TableCell colSpan={3} />
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Sentinel para IntersectionObserver */}
      <Box ref={sentinelRef} sx={{ height: 20, display: 'flex', justifyContent: 'center', alignItems: 'center', mt: 1 }}>
        {isLoadingMore && <CircularProgress size={24} />}
      </Box>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editId ? 'Editar Pago' : 'Nuevo Pago'}</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Fecha de Pago" type="date" value={form.fecha_pago} onChange={set('fecha_pago')} InputLabelProps={{ shrink: true }} required />
            <TextField label="Concepto" value={form.concepto} onChange={set('concepto')} required />
            <TextField label="Proveedor" value={form.proveedor} onChange={set('proveedor')} required />
            <Stack direction="row" spacing={2}>
              <TextField label="Monto" type="number" value={form.monto} onChange={set('monto')} required sx={{ flex: 1 }} />
              <TextField select label="Moneda" value={form.moneda} onChange={set('moneda')} sx={{ width: 100 }}>
                {MONEDAS.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
              </TextField>
            </Stack>
            <TextField label="Equivalente en CLP" type="number" value={form.monto_clp} onChange={set('monto_clp')}
              helperText="Monto equivalente en pesos chilenos (opcional)" />
            <Stack direction="row" spacing={2}>
              <TextField select label="Tipo" value={form.tipo} onChange={set('tipo')} sx={{ flex: 1 }}>
                {TIPOS.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
              </TextField>
              <TextField select label="Estado" value={form.estado} onChange={set('estado')} sx={{ flex: 1 }}>
                {ESTADOS.map((e) => <MenuItem key={e} value={e}>{e}</MenuItem>)}
              </TextField>
            </Stack>
            <TextField label="Fecha Solicitud" type="date" value={form.fecha_solicitud} onChange={set('fecha_solicitud')} InputLabelProps={{ shrink: true }} />
            <TextField label="Fecha Reembolso" type="date" value={form.fecha_reembolso} onChange={set('fecha_reembolso')} InputLabelProps={{ shrink: true }} />
            <TextField label="Comprobante" value={form.comprobante} onChange={set('comprobante')} />
            <TextField label="Notas" value={form.notas} onChange={set('notas')} multiline rows={2} />
            <Stack direction="row" spacing={2}>
              <Box sx={{ flex: 1 }}>
                <MultiImageDropZone
                  label="Imágenes de cobro"
                  existingImages={existingImagenesCobro}
                  newFiles={newImagenesCobro}
                  onFilesAdd={(files) => setNewImagenesCobro((prev) => [...prev, ...files])}
                  onNewFileRemove={(idx) => setNewImagenesCobro((prev) => prev.filter((_, i) => i !== idx))}
                  onExistingRemove={(imgId) => {
                    if (editId) {
                      api.delete(`/pagos/${editId}/imagen/${imgId}`).then(() => {
                        setExistingImagenesCobro((prev) => prev.filter((img) => img.id !== imgId));
                      });
                    }
                  }}
                />
              </Box>
              <Box sx={{ flex: 1 }}>
                <MultiImageDropZone
                  label="Imágenes de reembolso"
                  existingImages={existingImagenesReembolso}
                  newFiles={newImagenesReembolso}
                  onFilesAdd={(files) => setNewImagenesReembolso((prev) => [...prev, ...files])}
                  onNewFileRemove={(idx) => setNewImagenesReembolso((prev) => prev.filter((_, i) => i !== idx))}
                  onExistingRemove={(imgId) => {
                    if (editId) {
                      api.delete(`/pagos/${editId}/imagen/${imgId}`).then(() => {
                        setExistingImagenesReembolso((prev) => prev.filter((img) => img.id !== imgId));
                      });
                    }
                  }}
                />
              </Box>
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={handleSave}>Guardar</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
