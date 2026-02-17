import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Box, Button, TextField, Typography, Paper, Alert } from '@mui/material';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
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
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <Paper sx={{ p: 4, maxWidth: 400, width: '100%' }}>
        <Typography variant="h5" gutterBottom align="center">Control de Reembolsos</Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <form onSubmit={handleSubmit}>
          <TextField label="Usuario" fullWidth margin="normal" value={username} onChange={(e) => setUsername(e.target.value)} required />
          <TextField label="Contraseña" type="password" fullWidth margin="normal" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }}>Iniciar Sesión</Button>
        </form>
      </Paper>
    </Box>
  );
}
