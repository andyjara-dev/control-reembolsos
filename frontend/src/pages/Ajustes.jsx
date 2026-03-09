import { useEffect, useState } from 'react';
import {
  Typography, Stack, TextField, Button, Alert, CircularProgress,
  Paper, Divider,
} from '@mui/material';
import api from '../api';

const CLAVES = [
  'resend_api_key',
  'email_from',
  'email_copia',
  'email_asunto_template',
  'email_cuerpo_template',
];

const DEFAULTS = {
  resend_api_key: '',
  email_from: '',
  email_copia: '',
  email_asunto_template: 'Solicitud de $tipo - $concepto ($proveedor)',
  email_cuerpo_template: '',
};

export default function Ajustes() {
  const [config, setConfig] = useState(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/configuracion').then((r) => {
      const merged = { ...DEFAULTS };
      r.data.forEach(({ clave, valor }) => {
        if (CLAVES.includes(clave)) merged[clave] = valor ?? '';
      });
      setConfig(merged);
    }).catch(() => {
      setError('Error al cargar la configuración');
    }).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSuccess('');
    setError('');
    try {
      const items = CLAVES.map((clave) => ({ clave, valor: config[clave] || null }));
      await api.put('/configuracion', items);
      setSuccess('Configuración guardada correctamente');
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const set = (clave) => (e) => setConfig({ ...config, [clave]: e.target.value });

  if (loading) return <CircularProgress sx={{ mt: 4 }} />;

  return (
    <>
      <Typography variant="h5" sx={{ mb: 3 }}>Ajustes</Typography>

      <Paper sx={{ p: 3, maxWidth: 700 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Configuración de Email (Resend)</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Se usa <strong>Resend</strong> para enviar los emails. Necesitas una cuenta en{' '}
          <strong>resend.com</strong> y verificar tu dominio remitente.
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

        <Stack spacing={3}>
          <TextField
            label="Resend API Key"
            type="password"
            value={config.resend_api_key}
            onChange={set('resend_api_key')}
            helperText='Si muestra "***" ya está configurada. Limpiar e ingresar nueva clave para actualizar.'
            fullWidth
          />

          <Divider />

          <TextField
            label='Email remitente ("De:")'
            value={config.email_from}
            onChange={set('email_from')}
            placeholder="Tu Nombre <tucuenta@tudominio.com>"
            helperText="Debe ser un dominio verificado en Resend."
            fullWidth
          />

          <TextField
            label="Tu email (copia CC)"
            type="email"
            value={config.email_copia}
            onChange={set('email_copia')}
            helperText="Recibirás una copia de cada solicitud enviada como comprobante."
            fullWidth
          />

          <Divider />

          <TextField
            label="Plantilla de asunto"
            value={config.email_asunto_template}
            onChange={set('email_asunto_template')}
            helperText="Variables disponibles: $tipo, $concepto, $proveedor, $monto, $moneda, $fecha_pago"
            fullWidth
          />

          <TextField
            label="Plantilla de cuerpo (HTML)"
            value={config.email_cuerpo_template}
            onChange={set('email_cuerpo_template')}
            multiline
            rows={10}
            helperText="HTML del email. Variables: $tipo, $concepto, $proveedor, $monto, $moneda, $monto_clp, $fecha_pago, $comprobante, $notas. Dejar vacío para usar la plantilla por defecto."
            fullWidth
            inputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
          />

          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saving}
            sx={{ alignSelf: 'flex-start' }}
          >
            {saving ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
            Guardar ajustes
          </Button>
        </Stack>
      </Paper>
    </>
  );
}
