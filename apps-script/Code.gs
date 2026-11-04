/**
 * Rotas DM Field — backend no Google Sheets
 *
 * Recebe as visitas registradas na página (GitHub Pages) e grava na aba "Visitas".
 * Também devolve todos os registros para montar o resumo executivo da equipe.
 *
 * Como publicar: Implantar > Nova implantação > Tipo "App da Web"
 *   Executar como: Eu  ·  Quem pode acessar: Qualquer pessoa
 * Copie a URL que termina em /exec e cole em config.js (SHEETS_URL).
 */

const ABA = 'Visitas';
const COLUNAS = [
  'id', 'cod', 'cliente', 'desenvolvedor', 'dev', 'dataPlanejada', 'ts',
  'realizou', 'positivou', 'itens', 'motivo', 'obs', 'waAt', 'rev'
];
const TITULOS = [
  'ID', 'Cód. Cliente', 'Cliente', 'Desenvolvedor', 'Dev (índice)', 'Data planejada', 'Data/hora do registro',
  'Realizou atendimento', 'Positivou', 'O que positivou', 'Motivo não atendimento', 'Observação',
  'WhatsApp aberto em', 'Revisão'
];

function aba_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(ABA);
  if (!sh) {
    sh = ss.insertSheet(ABA);
    sh.getRange(1, 1, 1, TITULOS.length).setValues([TITULOS]).setFontWeight('bold');
    sh.setFrozenRows(1);
    sh.getRange('A:A').setNumberFormat('@');
    sh.getRange('F:F').setNumberFormat('@');
  }
  return sh;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function paraLinha_(r) {
  return COLUNAS.map(k => {
    const v = r[k];
    if (k === 'realizou' || k === 'positivou') return v === true ? 'SIM' : v === false ? 'NÃO' : '';
    if (k === 'itens') return (v || []).join(', ');
    if (k === 'ts' || k === 'waAt') return v ? Utilities.formatDate(new Date(v), 'America/Sao_Paulo', 'dd/MM/yyyy HH:mm:ss') : '';
    if (v === null || v === undefined) return '';
    if (typeof v === 'string' && /^[=+\-@]/.test(v)) return "'" + v; // evita virar fórmula
    return v;
  });
}

function deLinha_(row, raw) {
  const o = {};
  COLUNAS.forEach((k, i) => { o[k] = row[i]; });
  // ts/waAt originais em ISO ficam guardados na coluna oculta "raw" (última)
  const extra = raw ? JSON.parse(raw) : {};
  return {
    id: String(o.id), cod: Number(o.cod), dev: Number(o.dev), dataPlanejada: o.dataPlanejada instanceof Date ? Utilities.formatDate(o.dataPlanejada, 'America/Sao_Paulo', 'yyyy-MM-dd') : String(o.dataPlanejada),
    ts: extra.ts || '', waAt: extra.waAt || null,
    realizou: o.realizou === 'SIM', positivou: o.positivou === 'SIM' ? true : o.positivou === 'NÃO' ? false : null,
    itens: o.itens ? String(o.itens).split(', ') : [], motivo: o.motivo || null, obs: String(o.obs || ''),
    rev: Number(o.rev) || 1
  };
}

function doGet(e) {
  try {
    const sh = aba_();
    const n = sh.getLastRow() - 1;
    if (n < 1) return json_({ ok: true, records: [] });
    const vals = sh.getRange(2, 1, n, COLUNAS.length + 1).getValues();
    const records = vals.filter(r => r[0]).map(r => deLinha_(r, r[COLUNAS.length]));
    return json_({ ok: true, records });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const body = JSON.parse(e.postData.contents);
    if (body.action !== 'upsert' || !body.rec || !body.rec.id) return json_({ ok: false, error: 'pedido inválido' });
    const r = body.rec;
    const sh = aba_();
    const linha = paraLinha_(r).concat([JSON.stringify({ ts: r.ts, waAt: r.waAt || null })]);
    const n = sh.getLastRow() - 1;
    let alvo = -1;
    if (n > 0) {
      const ids = sh.getRange(2, 1, n, 1).getValues();
      for (let i = 0; i < ids.length; i++) if (String(ids[i][0]) === String(r.id)) { alvo = i + 2; break; }
    }
    if (alvo > 0) {
      const revAtual = Number(sh.getRange(alvo, COLUNAS.indexOf('rev') + 1).getValue()) || 0;
      if ((Number(r.rev) || 0) >= revAtual) sh.getRange(alvo, 1, 1, linha.length).setValues([linha]);
    } else {
      sh.appendRow(linha);
    }
    sh.hideColumns(COLUNAS.length + 1);
    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}
