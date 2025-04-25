const express = require('express');
const mongoose = require('mongoose');
const bodyParser = require('body-parser');
const multer = require('multer');
const path = require('path');

const app = express();
const port = 3000;

// Middleware
app.use(bodyParser.json());
app.use(express.static('uploads'));  // Pasta onde os arquivos serão armazenados

// Configuração do armazenamento para arquivos
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, 'uploads/');  // Armazenar na pasta 'uploads'
    },
    filename: function (req, file, cb) {
        cb(null, Date.now() + path.extname(file.originalname));  // Usar timestamp como nome
    }
});
const upload = multer({ storage: storage });

// Conectar ao MongoDB
mongoose.connect('mongodb://localhost/tutoria-digital', { useNewUrlParser: true, useUnifiedTopology: true })
    .then(() => console.log('MongoDB conectado!'))
    .catch((err) => console.log('Erro na conexão com MongoDB:', err));

// Esquema de dados para a tutoria
const tutoriaSchema = new mongoose.Schema({
    nomeAluno: String,
    serie: String,
    projetoVida: String,
    assuntoPessoal: String,
    telefoneCelular: String,
    carimboGestor: String,
    dataHora: String,
    assinaturaAluno: String,
    arquivos: [String]  // Para armazenar URLs dos arquivos enviados
});

const Tutoria = mongoose.model('Tutoria', tutoriaSchema);

// Rota para salvar a tutoria com arquivo
app.post('/salvarTutoria', upload.array('arquivos', 10), (req, res) => {
    const tutoriaData = {
        nomeAluno: req.body.nomeAluno,
        serie: req.body.serie,
        projetoVida: req.body.projetoVida,
        assuntoPessoal: req.body.assuntoPessoal,
        telefoneCelular: req.body.telefoneCelular,
        carimboGestor: req.body.carimboGestor,
        dataHora: new Date().toLocaleString(),
        assinaturaAluno: req.body.assinaturaAluno,  // Assinatura digital
        arquivos: req.files.map(file => file.path)  // Salvar caminho dos arquivos
    };

    const novaTutoria = new Tutoria(tutoriaData);

    novaTutoria.save()
        .then(() => res.json({ message: 'Tutoria salva com sucesso!' }))
        .catch(err => res.status(500).json({ error: err.message }));
});

// Rota para obter todas as tutorias
app.get('/tutorias', (req, res) => {
    Tutoria.find()
        .then(tutorias => res.json(tutorias))
        .catch(err => res.status(500).json({ error: err.message }));
});

// Iniciar o servidor
app.listen(port, () => {
    console.log(`Servidor rodando na porta ${port}`);
});
