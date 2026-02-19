import { useEffect, useState } from 'react';
import { Card, CardContent, Typography, Grid, Table, TableHead, TableRow, TableCell, TableBody, Chip, Box } from '@mui/material';
import api from '../api';

const estadoColor = { PENDIENTE: 'warning', SOLICITADO: 'info', PAGADO: 'success' };

export default function Dashboard() {
  const [resumen, setResumen] = useState(null);
  const [pendientes, setPendientes] = useState([]);

  useEffect(() => {
    api.get('/pagos/resumen').then((r) => setResumen(r.data));
    api.get('/pagos', { params: { estado: 'PENDIENTE' } }).then((r) => setPendientes(r.data));
  }, []);

  if (!resumen) return <Typography>Cargando...</Typography>;

  const cards = [
    { label: 'Pendiente Reembolso', value: resumen.total_pendiente_reembolso, color: '#FFB236' },
    { label: 'Pendiente Provisión', value: resumen.total_pendiente_provision, color: '#FF3636' },
    { label: 'Solicitado Reembolso', value: resumen.total_solicitado_reembolso, color: '#2CA8FF' },
    { label: 'Solicitado Provisión', value: resumen.total_solicitado_provision, color: '#7ee1ff' },
    { label: 'Pagado este mes', value: resumen.total_pagado_mes, color: '#0487a8' },
    { label: 'Pagos pendientes', value: resumen.cantidad_pendientes, color: '#2c2c2c', isCant: true },
  ];

  return (
    <>
      <Typography variant="h5" gutterBottom>Dashboard</Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {cards.map((c) => (
          <Grid item xs={12} sm={6} md={4} key={c.label}>
            <Card sx={{ borderLeft: `4px solid ${c.color}` }}>
              <CardContent>
                <Typography variant="body2" color="text.secondary">{c.label}</Typography>
                <Typography variant="h5">
                  {c.isCant ? c.value : `$${Number(c.value).toLocaleString('es-CL', { maximumFractionDigits: 0 })}`}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Typography variant="h6" gutterBottom>Pagos Pendientes</Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Fecha</TableCell>
            <TableCell>Concepto</TableCell>
            <TableCell>Proveedor</TableCell>
            <TableCell align="right">Monto</TableCell>
            <TableCell align="right">Monto CLP</TableCell>
            <TableCell>Tipo</TableCell>
            <TableCell>Estado</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {pendientes.map((p) => (
            <TableRow key={p.id}>
              <TableCell>{p.fecha_pago}</TableCell>
              <TableCell>{p.concepto}</TableCell>
              <TableCell>{p.proveedor}</TableCell>
              <TableCell align="right">{Number(p.monto).toFixed(2)} {p.moneda}</TableCell>
              <TableCell align="right">{p.monto_clp ? Number(p.monto_clp).toLocaleString('es-CL', { maximumFractionDigits: 0 }) : '-'}</TableCell>
              <TableCell><Chip label={p.tipo} size="small" /></TableCell>
              <TableCell><Chip label={p.estado} size="small" color={estadoColor[p.estado]} /></TableCell>
            </TableRow>
          ))}
          {pendientes.length === 0 && (
            <TableRow><TableCell colSpan={7} align="center">No hay pagos pendientes</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </>
  );
}
