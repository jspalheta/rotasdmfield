# Rotas DM Field · Novembro/2026

Página de rotas dos desenvolvedores (Goiânia e Trindade), com registro de visitas, envio no WhatsApp e resumo executivo. A página roda no GitHub Pages e as visitas ficam numa planilha do Google Sheets.

## Estrutura

| Arquivo | O que é |
|---|---|
| `index.html` | A página (rotas, tela do cliente, registro de visita, resumo executivo) |
| `config.js` | URL da planilha (Apps Script). É o único arquivo que precisa ser editado na instalação |
| `dados/rotas.js` | Base de 1.572 clientes já roteirizada (desenvolvedor, data e ordem de visita) |
| `dados/Roteirizacao_DM_Field_Nov26.xlsx` | A mesma roteirização em planilha |
| `dados/roteirizacao.py` | Script que gerou a divisão e as rotas |
| `apps-script/Code.gs` | Código que liga a página à planilha do Google Sheets |

## Ligar a planilha (uma vez)

1. Crie uma planilha no Google Sheets, por exemplo "Visitas DM Field".
2. Abra **Extensões › Apps Script**, apague o conteúdo e cole o arquivo `apps-script/Code.gs`. Salve.
3. Clique em **Implantar › Nova implantação**, escolha o tipo **App da Web** e preencha:
   - Executar como: **Eu**
   - Quem pode acessar: **Qualquer pessoa**
4. Autorize o acesso quando o Google pedir e copie a **URL do app da Web** (termina em `/exec`).
5. Cole a URL em `config.js`, em `SHEETS_URL`, e salve o arquivo no repositório.

A aba **Visitas** é criada sozinha no primeiro registro. Cada linha guarda uma visita: cliente, desenvolvedor, data/hora, se realizou, se positivou, o que positivou, motivo, observação e quando o WhatsApp foi aberto.

> Se você alterar o `Code.gs` depois, use **Implantar › Gerenciar implantações › Editar › Nova versão** para manter a mesma URL.

## Como funciona o registro

- A visita é salva primeiro no celular e depois enviada para a planilha. Sem internet, ela fica guardada e sobe sozinha quando a conexão volta.
- A página busca os registros da planilha a cada minuto para atualizar o resumo da equipe.
- O botão de WhatsApp abre a conversa com a mensagem pronta. A página não consegue confirmar o envio, por isso registra o horário em que o WhatsApp foi aberto.

## Publicar no GitHub Pages

Em **Settings › Pages**, escolha a branch `main` e a pasta `/ (root)`. O link fica `https://<usuario>.github.io/<repositorio>/`.

Links diretos para cada desenvolvedor: `#altobeli`, `#andre`, `#fabricio`, `#joao-victor`, `#rafael`, `#yucanna`. Resumo da equipe: `#resumo`.
