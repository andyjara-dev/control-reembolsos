import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Box, Button, TextField, Typography, Paper, Alert,
  Dialog, DialogTitle, DialogContent, DialogActions, Link,
  CircularProgress,
} from '@mui/material';
import axios from 'axios';

function ReembolsosLogo({ width = 260 }) {
  return (
    <svg
      viewBox="0 0 280 72"
      width={width}
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Reembolsos logo"
    >
      <defs>
        <linearGradient id="bagTop" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#60c8ff" />
          <stop offset="100%" stopColor="#1a7fd4" />
        </linearGradient>
        <linearGradient id="bagBody" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#1570b8" />
        </linearGradient>
        <linearGradient id="sGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#818cf8" />
        </linearGradient>
      </defs>

      {/* Bag knot */}
      <ellipse cx="36" cy="20" rx="10" ry="5" fill="#0d5fa8" />

      {/* Bag neck */}
      <rect x="29" y="20" width="14" height="10" rx="1" fill="url(#bagTop)" />

      {/* Bag body */}
      <ellipse cx="36" cy="48" rx="22" ry="20" fill="url(#bagBody)" />

      {/* Return arrow */}
      <path
        d="M24 52 A13 13 0 0 1 48 52"
        stroke="white"
        strokeWidth="3.5"
        fill="none"
        strokeLinecap="round"
      />
      <polygon points="24,45 17,52 24,59" fill="white" />

      {/* reembolso + s */}
      <text fontFamily="Arial, sans-serif" fontWeight="bold" fontSize="30" y="54" x="68">
        <tspan fill="white">reembolso</tspan>
        <tspan fill="url(#sGrad)">s</tspan>
      </text>

      {/* subtitle */}
      <text
        x="68"
        y="69"
        fontFamily="Arial, sans-serif"
        fontSize="12"
        fill="#475569"
        letterSpacing="0.5"
      >
        .andyjara.dev
      </text>
    </svg>
  );
}

function OlvidePasswordDialog({ open, onClose }) {
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg('');
    setError('');
    try {
      await axios.post('/api/auth/olvide-password', { username });
      setMsg('Si el usuario existe y tiene email configurado, recibirás un correo con tu nueva contraseña temporal.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al procesar la solicitud.');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setUsername('');
    setMsg('');
    setError('');
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle>Restablecer contraseña</DialogTitle>
      <form onSubmit={handleSubmit}>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Ingresa tu nombre de usuario. Si tienes un email configurado en tu perfil, recibirás una contraseña temporal.
          </Typography>
          {msg && <Alert severity="success" sx={{ mb: 2 }}>{msg}</Alert>}
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {!msg && (
            <TextField
              label="Usuario"
              fullWidth
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handleClose} color="inherit">Cerrar</Button>
          {!msg && (
            <Button type="submit" variant="contained" disabled={loading}>
              {loading ? <CircularProgress size={20} /> : 'Enviar'}
            </Button>
          )}
        </DialogActions>
      </form>
    </Dialog>
  );
}

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [olvideOpen, setOlvideOpen] = useState(false);
  const { login, isAuth } = useAuth();
  const navigate = useNavigate();

  if (isAuth) {
    navigate('/');
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await login(username, password);
      navigate('/');
    } catch {
      setError('Credenciales inválidas');
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        bgcolor: 'background.default',
        px: 2,
      }}
    >
      <Box sx={{ mb: 4 }}>
        <ReembolsosLogo width={240} />
      </Box>

      <Paper
        elevation={0}
        sx={{
          p: 4,
          maxWidth: 420,
          width: '100%',
          bgcolor: 'background.paper',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 2,
        }}
      >
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <form onSubmit={handleSubmit}>
          <TextField
            label="Usuario"
            fullWidth
            margin="normal"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="username"
          />
          <Box sx={{ position: 'relative' }}>
            <TextField
              label="Contraseña"
              type="password"
              fullWidth
              margin="normal"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.5 }}>
              <Link
                component="button"
                type="button"
                variant="caption"
                color="primary"
                onClick={() => setOlvideOpen(true)}
                sx={{ cursor: 'pointer', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
              >
                ¿Olvidaste tu contraseña?
              </Link>
            </Box>
          </Box>

          <Button
            type="submit"
            variant="contained"
            fullWidth
            sx={{ mt: 2.5, py: 1.3, fontSize: '1rem' }}
          >
            Ingresar
          </Button>
        </form>
      </Paper>

      <Typography variant="caption" color="text.secondary" sx={{ mt: 3 }}>
        Control de Reembolsos © {new Date().getFullYear()}
      </Typography>

      <OlvidePasswordDialog open={olvideOpen} onClose={() => setOlvideOpen(false)} />
    </Box>
  );
}
