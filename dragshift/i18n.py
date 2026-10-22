"""Tiny translation layer: English source strings → Portuguese (Brazil).

`tr("Converting to {name}…", name="PNG")` returns the translated text (or the English
original when the language is English or there is no translation yet). Keys keep `{name}`
placeholders so word order can change between languages.

The language is "auto" by default (follows the system), or forced in Settings.
"""
from __future__ import annotations

LANG = "en"
LANGUAGES = [("auto", "Automatic (system)"), ("pt", "Português (Brasil)"), ("en", "English")]


def system_language() -> str:
    try:
        from PySide6.QtCore import QLocale
        name = QLocale.system().name().lower()   # e.g. "pt_br"
    except Exception:  # pragma: no cover
        import locale
        name = (locale.getlocale()[0] or "").lower()
    return "pt" if name.startswith("pt") else "en"


def set_language(code: str) -> str:
    """'auto' | 'pt' | 'en' → the language actually used."""
    global LANG
    LANG = system_language() if code in (None, "", "auto") else ("pt" if code == "pt" else "en")
    return LANG


def tr(text: str, **kw) -> str:
    if LANG == "pt":
        text = PT.get(text, text)
    return text.format(**kw) if kw else text


def plural(n: int, one: str, many: str, **kw) -> str:
    """plural(3, "{n} file", "{n} files") → "3 arquivos" in Portuguese."""
    return tr(one if n == 1 else many, n=n, **kw)


# Rename patterns: the braces here are tokens the user types ({nome}, {data}), not format fields
TOKEN_STRINGS = {"{name} {n}", "{date} {name}", "{date} {n}",
                 "{name} = current name · {n} = number · {date} = photo date or modified date"}

PT: dict[str, str] = {
    # ---------------------------------------------------------------- tray / app
    "Enabled": "Ativado",
    "Open a file…": "Abrir um arquivo…",
    "Settings…": "Configurações…",
    "How to use": "Como usar",
    "Tip the developer ♥": "Apoiar o desenvolvedor original ♥",
    "Quit {app}": "Sair do {app}",
    "{app} — press {key} while dragging a file": "{app} — aperte {key} enquanto arrasta um arquivo",
    "DragShift is already running": "O DragShift já está aberto",
    "Drag any file and press {key}. It lives in the tray.":
        "Arraste qualquer arquivo e aperte {key}. Ele fica na bandeja do sistema.",
    "DragShift is running": "O DragShift está rodando",
    "Drag any file, then press {key}.": "Arraste qualquer arquivo e aperte {key}.",
    "Choose file(s) for DragShift": "Escolha arquivo(s) para o DragShift",
    "Couldn't open {name}": "Não foi possível abrir {name}",
    "Couldn't finish": "Não foi possível concluir",
    "Working…": "Processando…",
    "No permission to write next to this file. Try a folder you own, or set Settings → Save results → subfolder.":
        "Sem permissão para salvar ao lado deste arquivo. Use uma pasta sua ou mude em "
        "Configurações → Salvar resultados → subpasta.",
    "This file doesn't look like an image DragShift can read.":
        "Este arquivo não parece ser uma imagem que o DragShift consiga ler.",
    "The file was moved or deleted.": "O arquivo foi movido ou apagado.",
    "Combining {n} images…": "Juntando {n} imagens…",
    "Converting to {name}…": "Convertendo para {name}…",
    "Merging…": "Mesclando…",
    "Compressing…": "Comprimindo…",
    "Splitting…": "Dividindo…",
    "Rotating…": "Girando…",
    "Extracting images…": "Extraindo imagens…",
    "{n} file": "{n} arquivo",
    "{n} files": "{n} arquivos",
    "{n} images → 1 PDF": "{n} imagens → 1 PDF",

    # ---------------------------------------------------------------- radial menu
    "Convert": "Converter",
    "Tools": "Ferramentas",
    "Unsupported": "Não suportado",
    "Drop here": "Solte aqui",
    "Can't convert {ext}": "Não converte {ext}",
    "this file": "este arquivo",
    "Images · PDF · Word · Text": "Imagens · PDF · Word · Texto",
    # tool names
    "Compress": "Comprimir", "Metadata": "Metadados", "Redact": "Ocultar", "Crop": "Cortar",
    "Edit": "Ajustar", "Annotate": "Anotar", "Add BG": "Fundo", "Resize": "Redimensionar",
    "Split": "Dividir", "Rotate": "Girar", "Merge": "Mesclar", "Protect": "Proteger",
    "Extract": "Extrair",
    # tool hints
    "Shrink file size": "Reduzir o tamanho", "View · remove GPS": "Ver · remover GPS",
    "Hide private info": "Esconder dados privados", "Trim to a ratio": "Recortar numa proporção",
    "Light · colour · rotate": "Luz · cor · girar", "Arrows · text · steps": "Setas · texto · passos",
    "Gradient backdrop": "Fundo em degradê", "Change dimensions": "Mudar as dimensões",
    "One PDF per page": "Um PDF por página", "Turn pages 90°": "Girar páginas 90°",
    "Join in any order": "Juntar na ordem que quiser", "Add a password": "Adicionar senha",
    "Save embedded images": "Salvar as imagens internas",
    # format hints
    "Small, universal": "Leve, universal", "Lossless · transparency": "Sem perdas · transparência",
    "Smallest for web": "Menor para web", "iPhone format": "Formato do iPhone",
    "Print · archival": "Impressão · arquivo", "Next-gen, tiny": "Nova geração, minúsculo",
    "Uncompressed": "Sem compressão", "Document": "Documento", "Windows icon": "Ícone do Windows",
    "Legacy web": "Web antiga", "Editable Word": "Word editável", "Plain text": "Texto simples",

    # ---------------------------------------------------------------- notifications
    "Open": "Abrir",
    "Show in folder": "Mostrar na pasta",
    "Undo": "Desfazer",
    "Undone": "Desfeito",
    "Moved {n} file to the {bin}": "{n} arquivo movido para a {bin}",
    "Moved {n} files to the {bin}": "{n} arquivos movidos para a {bin}",
    "Recycle Bin": "Lixeira",
    "Trash": "Lixeira",
    "Nothing was written": "Nenhum arquivo foi gerado",
    "{a}% smaller": "{a}% menor",
    "{a}% larger": "{a}% maior",
    "same size": "mesmo tamanho",
    "already well compressed": "já estava bem comprimido",
    "{n} files → 1 {fmt}": "{n} arquivos → 1 {fmt}",
    "{p} pages → {n} {fmt}s": "{p} páginas → {n} {fmt}",
    "{n} files → {fmt}": "{n} arquivos → {fmt}",
    "{n} page": "{n} página",
    "{n} pages": "{n} páginas",
    "Compressed": "Comprimido",
    "Compressed {n} files": "{n} arquivos comprimidos",
    "Cropped": "Cortado",
    "Resized": "Redimensionado",
    "Edited": "Editado",
    "Cropped {n} images": "{n} imagens cortadas",
    "Resized {n} images": "{n} imagens redimensionadas",
    "Edited {n} images": "{n} imagens editadas",
    "Background added": "Fundo adicionado",
    "Annotated": "Anotado",
    "Redacted": "Ocultado",
    "burned into pixels": "gravado nos pixels",
    "Metadata removed": "Metadados removidos",
    "private copy": "cópia privada",
    "Split into {n} PDFs": "Dividido em {n} PDFs",
    "Merged {n} PDFs": "{n} PDFs mesclados",
    "Rotated 90°": "Girado 90°",
    "Password protected": "Protegido por senha",
    "encrypted": "criptografado",
    "Extracted {n} image": "{n} imagem extraída",
    "Extracted {n} images": "{n} imagens extraídas",

    # ---------------------------------------------------------------- output file names
    "Combined": "Combinado",
    "With Background": "Com fundo",
    "No Location": "Sem localização",
    "Clean": "Limpo",
    "Merged": "Mesclado",
    "Protected": "Protegido",
    "Rotated": "Girado",
    "page {n}": "página {n}",
    "page {p} image {n}": "página {p} imagem {n}",
    "{name} images": "{name} imagens",

    # ---------------------------------------------------------------- errors from processing
    "This PDF is password-protected. Remove the password first.":
        "Este PDF tem senha. Remova a senha primeiro.",
    "No images found in this PDF.": "Nenhuma imagem encontrada neste PDF.",

    # ---------------------------------------------------------------- settings / welcome
    "Settings": "Configurações",
    "Open the menu with": "Abrir o menu com",
    "…pressed while you’re dragging a file": "…pressionado enquanto você arrasta um arquivo",
    "Save results": "Salvar resultados",
    "Next to the original": "Ao lado do original",
    "In a “DragShift” subfolder": "Numa subpasta “DragShift”",
    "JPG / WebP quality": "Qualidade JPG / WebP",
    "PDF → image resolution": "Resolução PDF → imagem",
    "150 dpi · small": "150 dpi · pequeno",
    "200 dpi · balanced": "200 dpi · equilibrado",
    "300 dpi · print": "300 dpi · impressão",
    "Language": "Idioma",
    "Automatic (system)": "Automático (sistema)",
    "Takes effect after restarting DragShift": "Vale depois de reiniciar o DragShift",
    "Start DragShift with Windows": "Iniciar o DragShift com o Windows",
    "Open DragShift at login": "Abrir o DragShift ao entrar",
    "Enable full liquid glass…": "Ativar vidro líquido completo…",
    "Lets the glass refract the windows behind it (Screen Recording permission)":
        "Deixa o vidro refratar as janelas atrás dele (permissão de Gravação de Tela)",
    "DragShift {v}  ·  originals are never modified": "DragShift {v}  ·  os originais nunca são alterados",
    "Done": "Concluir",
    "Welcome to DragShift": "Bem-vindo ao DragShift",
    "Start dragging any file": "Comece a arrastar qualquer arquivo",
    "in Finder or on the desktop": "no Finder ou na mesa",
    "in your file manager (Thunar, Nautilus…)": "no gerenciador de arquivos (Thunar, Nautilus…)",
    "in File Explorer or on the desktop": "no Explorador de Arquivos ou na área de trabalho",
    "Press {key}": "Aperte {key}",
    "the glass menu opens right under your cursor": "o menu de vidro abre logo embaixo do cursor",
    "Drop it on a slice": "Solte numa fatia",
    "the result is saved next to the original": "o resultado é salvo ao lado do original",
    "Tap {key} again": "Aperte {key} de novo",
    "to switch between Convert and Tools": "para alternar entre Converter e Ferramentas",
    "Optional: allow Screen Recording so the glass can refract the windows behind it (otherwise it shows your wallpaper). DragShift never saves or sends it.":
        "Opcional: permita a Gravação de Tela para o vidro refratar as janelas atrás dele (senão ele "
        "mostra o papel de parede). O DragShift nunca salva nem envia nada.",
    "Allow Screen Recording…": "Permitir Gravação de Tela…",
    "You're on a Wayland session: the Shift-while-dragging trigger needs X11 (e.g. XFCE). Right-click a file → Open With → DragShift still works.":
        "Você está numa sessão Wayland: o atalho de Shift ao arrastar precisa de X11 (ex.: XFCE). "
        "Botão direito no arquivo → Abrir com → DragShift continua funcionando.",
    "Start with Windows": "Iniciar com o Windows",
    "Open at login": "Abrir ao entrar",
    "Got it": "Entendi",

    # ---------------------------------------------------------------- tool windows: common
    "Reset": "Redefinir",
    "Cancel": "Cancelar",
    "Apply": "Aplicar",
    "Save": "Salvar",
    "Redo": "Refazer",
    "Copy": "Copiar",
    "Copied ✓": "Copiado ✓",
    "Copy image": "Copiar imagem",
    "Image copied ✓": "Imagem copiada ✓",
    "Size": "Tamanho",
    "Show": "Mostrar",
    "Close (Esc)": "Fechar (Esc)",
    "flipped": "espelhado",
    "⚠  This photo reveals where it was taken.": "⚠  Esta foto revela onde foi tirada.",
    "{name}  ·  {size}": "{name}  ·  {size}",
    "{n} files  ·  {size}": "{n} arquivos  ·  {size}",

    # crop
    "Crop Image": "Cortar imagem",
    "Aspect ratio": "Proporção",
    "Free": "Livre",
    "Original": "Original",
    "Rotate 90°": "Girar 90°",
    "Double-click the image to reset": "Clique duas vezes na imagem para redefinir",
    "Cropping…": "Cortando…",
    "rotated {n}°": "girado {n}°",

    # add background
    "Background": "Fundo",
    "Custom colour": "Cor personalizada",
    "Background colour": "Cor do fundo",
    "Padding": "Margem",
    "Corners": "Cantos",
    "Shadow": "Sombra",
    "Angle": "Ângulo",
    "Auto": "Auto",
    "Copy the result to the clipboard": "Copiar o resultado para a área de transferência",
    "Save with Background": "Salvar com fundo",
    "Output  {dims} px  ·  PNG": "Saída  {dims} px  ·  PNG",
    "Adding background…": "Adicionando fundo…",
    "Sunset": "Pôr do sol", "Prism": "Prisma", "Peach": "Pêssego", "Aurora": "Aurora",
    "Mint": "Menta", "Ocean": "Oceano", "Dusk": "Crepúsculo", "Lemon": "Limão",
    "Night": "Noite", "Rose": "Rosa",

    # annotate
    "➜ Arrow": "➜ Seta", "▢ Box": "▢ Caixa", "◯ Circle": "◯ Círculo", "✎ Pen": "✎ Caneta",
    "▬ Marker": "▬ Marca-texto", "T Text": "T Texto", "① Step": "① Passo",
    "Type, then Enter": "Digite e tecle Enter",
    "Saving annotations…": "Salvando anotações…",
    "{n} arrow": "{n} seta", "{n} arrows": "{n} setas",
    "{n} box": "{n} caixa", "{n} boxs": "{n} caixas",
    "{n} circle": "{n} círculo", "{n} circles": "{n} círculos",
    "{n} stroke": "{n} traço", "{n} strokes": "{n} traços",
    "{n} highlight": "{n} destaque", "{n} highlights": "{n} destaques",
    "{n} label": "{n} texto", "{n} labels": "{n} textos",
    "{n} step": "{n} passo", "{n} steps": "{n} passos",

    # redact
    "Black box": "Tarja preta",
    "Pixelate": "Pixelizar",
    "Blur": "Desfocar",
    "Drag over anything you want hidden. It's burned into the pixels — it can't be undone in the copy.":
        "Arraste sobre o que quiser esconder. Fica gravado nos pixels — não dá para desfazer na cópia.",
    "{name}  ·  {n} area hidden": "{name}  ·  {n} área oculta",
    "{name}  ·  {n} areas hidden": "{name}  ·  {n} áreas ocultas",
    "Redacting…": "Ocultando…",
    "{n} area {mode}": "{n} área ({mode})",
    "{n} areas {mode}": "{n} áreas ({mode})",
    "black box": "tarja preta", "pixelate": "pixelizada", "blur": "desfocada",

    # edit
    "Brightness": "Brilho", "Contrast": "Contraste", "Saturation": "Saturação",
    "Warmth": "Temperatura", "Sharpness": "Nitidez",
    "✦ Auto": "✦ Auto",
    "Automatic light and colour": "Luz e cor automáticas",
    "⇋ Flip": "⇋ Espelhar", "⇵ Flip": "⇵ Espelhar",
    "B&&W": "P&&B",
    "B&W": "P&B",
    "Hold to compare": "Segure para comparar",
    "Applying edits…": "Aplicando edições…",

    # metadata
    "No personal metadata found.": "Nenhum metadado pessoal encontrado.",
    "Open map": "Abrir mapa",
    "Show all {n} fields": "Mostrar todos os {n} campos",
    "Show fewer": "Mostrar menos",
    "Field": "Campo",
    "Value": "Valor",
    "Remove location only": "Remover só a localização",
    "Remove all metadata": "Remover todos os metadados",
    "removed {n} field": "{n} campo removido",
    "removed {n} fields": "{n} campos removidos",
    " incl. GPS location": " incl. localização GPS",
    "Removing metadata…": "Removendo metadados…",
    "Removing location…": "Removendo localização…",
    "GPS removed, camera info kept": "GPS removido, dados da câmera mantidos",
    "Camera": "Câmera", "Taken": "Data", "Software": "Software", "Exposure": "Exposição",
    "Aperture": "Abertura", "ISO": "ISO", "Location": "Localização", "Pages": "Páginas",
    "Dimensions": "Dimensões", "Format": "Formato", "Mode": "Modo",

    # compress
    "Quality": "Qualidade",
    "Target size": "Tamanho-alvo",
    "Make each file under": "Deixar cada arquivo abaixo de",
    "Original size": "Manter o original",
    "Max {n} px": "Máx. {n} px",
    "Convert to WebP (usually the smallest)": "Converter para WebP (geralmente o menor)",
    "Compress {n} files": "Comprimir {n} arquivos",
    "quality ≈ {q}": "qualidade ≈ {q}",
    "≈ {pct}% smaller · {fmt}": "≈ {pct}% menor · {fmt}",
    "Already well compressed — try a smaller size or WebP":
        "Já está bem comprimido — tente um tamanho menor ou WebP",
    "target {label}": "alvo {label}",
    "quality {q}": "qualidade {q}",

    # resize
    "Presets — percent or longest side in px": "Predefinições — porcentagem ou lado maior em px",
    "Exact size": "Tamanho exato",
    "Keep proportions": "Manter proporções",
    "W": "L", "H": "A",
    "Resize {n} files": "Redimensionar {n} arquivos",
    "Resizing…": "Redimensionando…",

    # protect
    "Password-protect PDF": "Proteger PDF com senha",
    "Password": "Senha",
    "Confirm": "Confirmar",
    "AES-256 encryption. Anyone opening the PDF will need this password.":
        "Criptografia AES-256. Quem abrir o PDF vai precisar desta senha.",
    "Use at least 4 characters.": "Use pelo menos 4 caracteres.",
    "Passwords don't match yet.": "As senhas ainda não conferem.",
    "Looks good · {s} password": "Tudo certo · senha {s}",
    "strong": "forte", "okay": "razoável", "weak": "fraca",
    "Encrypting…": "Criptografando…",

    # pdf snip
    "Snip": "Recortar",
    "Area → image": "Trecho → imagem",
    "Snip from PDF": "Recortar trecho do PDF",
    "Drag over the part you want": "Arraste sobre o trecho que você quer",
    "Previous page (Page Up)": "Página anterior (Page Up)",
    "Next page (Page Down)": "Próxima página (Page Down)",
    "Page {p} of {n}": "Página {p} de {n}",
    "Copy the snip to paste it anywhere (Ctrl+C)": "Copiar a imagem do trecho para colar em qualquer lugar (Ctrl+C)",
    "Save PNG": "Salvar PNG",
    "Saving snip…": "Salvando recorte…",
    "Snip saved": "Recorte salvo",
    "page {n} snip": "página {n} recorte",

    # organize / merge / extract
    "Organize": "Organizar",
    "Reorder · rotate · delete · extract": "Reordenar · girar · apagar · extrair",
    "Organize pages": "Organizar páginas",
    "Merge PDFs": "Mesclar PDFs",
    "Rotate selected pages left": "Girar páginas selecionadas para a esquerda",
    "Rotate selected pages right": "Girar páginas selecionadas para a direita",
    "🗑 Delete": "🗑 Apagar",
    "Remove the selected pages (Delete)": "Remover as páginas selecionadas (Delete)",
    "Drag pages to reorder · Ctrl/Shift+click to select several":
        "Arraste as páginas para reordenar · Ctrl/Shift+clique para selecionar várias",
    "Sort files by name": "Ordenar arquivos por nome",
    "Select pages": "Selecionar páginas",
    "e.g. 1-3, 7": "ex.: 1-3, 7",
    "Save selected only": "Salvar só as selecionadas",
    "New PDF with just the selected pages (extract)": "Novo PDF só com as páginas selecionadas (extrair)",
    "Save PDF": "Salvar PDF",
    "{n} selected": "{n} selecionada(s)",
    "Use page numbers like 1-3, 7, 10": "Use números de página como 1-3, 7, 10",
    "No pages to save.": "Nenhuma página para salvar.",
    "Saving PDF…": "Salvando PDF…",
    "Saving pages…": "Salvando páginas…",
    "Organized": "Organizado",
    "Extracted": "Extraído",
    "Pages extracted": "Páginas extraídas",
    "PDFs merged": "PDFs mesclados",
    "Pages organized": "Páginas organizadas",

    # searchable PDF (OCR)
    "OCR": "OCR",
    "Make a scan searchable": "Tornar escaneado pesquisável",
    "Recognising text ({n} pages)…": "Reconhecendo texto ({n} páginas)…",
    "Searchable": "Pesquisável",
    "Searchable PDF": "PDF pesquisável",
    "Ctrl+F works": "Ctrl+F funciona",
    "No text found to recognise in this PDF.": "Nenhum texto encontrado para reconhecer neste PDF.",
    "This PDF already has selectable text.": "Este PDF já tem texto selecionável.",

    # remove background
    "Cutout": "Sem fundo",
    "Remove the background (AI)": "Remover o fundo (IA)",
    "Removing background…": "Removendo fundo…",
    "Downloading the AI model (once, ~170 MB)…": "Baixando o modelo de IA (só uma vez, ~170 MB)…",
    "No Background": "Sem fundo",
    "Background removed": "Fundo removido",
    "Background removed from {n} images": "Fundo removido de {n} imagens",
    "transparent PNG": "PNG transparente",
    "Couldn't remove the background": "Não foi possível remover o fundo",
    "Couldn't download the background-removal model. Check your internet connection and try again.":
        "Não foi possível baixar o modelo de remoção de fundo. Verifique a internet e tente de novo.",
    "The downloaded model is corrupted. Try again.": "O modelo baixado veio corrompido. Tente de novo.",

    # spreadsheets
        "Excel spreadsheet": "Planilha do Excel",
    "Comma/semicolon text": "Texto separado por ;",
    "This spreadsheet couldn't be opened (is it password-protected?).":
        "Não foi possível abrir esta planilha (ela tem senha?).",
    "This spreadsheet is empty.": "Esta planilha está vazia.",
    "This file is empty.": "Este arquivo está vazio.",

    # video / audio
    "Images · PDF · Office · Video · Audio": "Imagens · PDF · Office · Vídeo · Áudio",
    "Plays everywhere": "Toca em qualquer lugar",
    "Audio only": "Só o áudio",
    "Uncompressed audio": "Áudio sem compressão",
    "Apple / small audio": "Áudio leve (Apple)",
    "Smaller MP4 (720p)": "MP4 menor (720p)",
    "First {n} s, 640 px": "Primeiros {n} s, 640 px",
    "Compressing video…": "Comprimindo vídeo…",
    "The video component isn't installed yet. Open DragShift with “Iniciar DragShift.bat” once to install it.":
        "O componente de vídeo ainda não está instalado. Abra o DragShift uma vez pelo “Iniciar DragShift.bat” para instalar.",
    "This file doesn't look like a video or audio DragShift can read.":
        "Este arquivo não parece ser um vídeo ou áudio que o DragShift consiga ler.",
    "This file has no video.": "Este arquivo não tem vídeo.",
    "This file has no audio.": "Este arquivo não tem áudio.",

    # batch rename
    "Rename": "Renomear",
    "Rename all with a pattern": "Renomear todos com um padrão",
    "Rename files": "Renomear arquivos",
    "New name": "Novo nome",
    "{name} {n}": "{nome} {n}",
    "Photo {n}": "Foto {n}",
    "{date} {name}": "{data} {nome}",
    "{date} {n}": "{data} {n}",
    "{name} = current name · {n} = number · {date} = photo date or modified date":
        "{nome} = nome atual · {n} = número · {data} = data da foto ou de modificação",
    "Start at": "Começar em",
    "Order": "Ordem",
    "Current order": "Ordem atual",
    "By name": "Por nome",
    "By date (photo taken / modified)": "Por data (foto / modificação)",
    "Current name": "Nome atual",
    "{n} name(s) can't be used: {why}": "{n} nome(s) não pode(m) ser usado(s): {why}",
    "{n} file will be renamed": "{n} arquivo será renomeado",
    "{n} files will be renamed": "{n} arquivos serão renomeados",
    "empty name": "nome vazio",
    'not allowed: < > : " / \\ | ? *': 'não é permitido: < > : " / \\ | ? *',
    "reserved name": "nome reservado do Windows",
    "name too long": "nome longo demais",
    "duplicate name": "nome repetido",
    "a file with this name already exists": "já existe um arquivo com esse nome",
    "Some names can't be used. Fix the ones marked in red.": "Alguns nomes não podem ser usados. Corrija os marcados em vermelho.",
    "Renamed {n} file": "{n} arquivo renomeado",
    "Renamed {n} files": "{n} arquivos renomeados",
    "Renamed {n} file back": "{n} arquivo voltou ao nome original",
    "Renamed {n} files back": "{n} arquivos voltaram ao nome original",
    "Couldn't undo": "Não foi possível desfazer",

    # pdf tables
    "Tables → Excel": "Tabelas → Excel",
    "No tables found. This looks like a scanned PDF: run OCR first.":
        "Nenhuma tabela encontrada. Parece um PDF escaneado: rode o OCR antes.",
    "No tables found in this PDF.": "Nenhuma tabela encontrada neste PDF.",

    # compress pdf
    "Compress PDF": "Comprimir PDF",
    "Balanced": "Equilibrado",
    "Images resampled to 150 dpi, text and vectors untouched. Usually 40–80% smaller.":
        "Imagens reamostradas para 150 dpi, texto e vetores intactos. Em geral 40–80% menor.",
    "Other": "Outro",
    "Keeps the best quality that fits. PDFs that are only text are already small and may not shrink much.":
        "Mantém a melhor qualidade que couber. PDFs só de texto já são leves e podem não diminuir muito.",

    # sign
    "Sign": "Assinar",
    "Place your signature": "Colocar sua assinatura",
    "Sign PDF": "Assinar PDF",
    "Signed": "Assinado",
    "PDF signed": "PDF assinado",
    "Signing…": "Assinando…",
    "every page": "todas as páginas",
    "Same place on every page": "Mesmo lugar em todas as páginas",
    "✎ Draw": "✎ Desenhar",
    "⬆ From photo": "⬆ De uma foto",
    "Photo or scan of your signature on white paper": "Foto ou scan da sua assinatura em papel branco",
    "Delete the selected signature": "Apagar a assinatura selecionada",
    "Photo of your signature": "Foto da sua assinatura",
    "Draw signature": "Desenhar assinatura",
    "Sign here with the mouse": "Assine aqui com o mouse",
    "Black": "Preto",
    "Blue": "Azul",
    "Clear": "Limpar",
    "Save signature": "Salvar assinatura",
    "Click or drag on the page to place the signature": "Clique ou arraste na página para posicionar a assinatura",
    "Pick or create a signature first": "Escolha ou crie uma assinatura primeiro",
    "The signature is empty.": "A assinatura está vazia.",
    "No signature found in this image. Use a photo of dark ink on light paper.":
        "Nenhuma assinatura encontrada na imagem. Use uma foto de tinta escura em papel claro.",

    # data
    "PARQUET": "PARQUET",
    "Columnar, for data tools": "Colunar, p/ ferramentas de dados",
    "For APIs and code": "Para APIs e código",
    "Peek": "Espiar",
    "integer": "inteiro", "decimal": "decimal", "boolean": "booleano", "date/time": "data/hora",
    "date": "data", "text": "texto", "empty": "vazio",
    "Columns, types, empty values": "Colunas, tipos, vazios",
    "Combine": "Juntar",
    "Stack into one file": "Empilhar num arquivo só",
    "Combining {n} files…": "Juntando {n} arquivos…",
    "Combined": "Combinado",
    "Combined {n} files": "{n} arquivos juntados",
    "+ source column": "+ coluna de origem",
    "{n} row": "{n} linha",
    "{n} rows": "{n} linhas",
    "Peek data": "Espiar dados",
    "Columns": "Colunas",
    "First rows": "Primeiras linhas",
    "Column": "Coluna",
    "Type": "Tipo",
    "Empty": "Vazios",
    "Distinct": "Distintos",
    "Min": "Mín",
    "Max": "Máx",
    "Example": "Exemplo",
    "Copy column list": "Copiar lista de colunas",
    "Name and type of every column, to paste anywhere": "Nome e tipo de cada coluna, para colar onde quiser",
    "Close": "Fechar",
    "{rows} rows × {cols} columns": "{rows} linhas × {cols} colunas",
    "The data component isn't installed yet. Open DragShift with “Iniciar DragShift.bat” once to install it.":
        "O componente de dados ainda não está instalado. Abra o DragShift uma vez pelo “Iniciar DragShift.bat” para instalar.",
    "This Parquet file couldn't be read.": "Não foi possível ler este arquivo Parquet.",
    "This JSON isn't a table (expected a list of records).": "Este JSON não é uma tabela (esperava uma lista de registros).",

    # collage
    "Collage": "Juntar",
    "Collage file": "Colagem",
    "Side by side or grid": "Lado a lado ou em grade",
    "Combine images": "Juntar imagens",
    "Layout": "Disposição",
    "Side by side": "Lado a lado",
    "Stacked": "Empilhado",
    "Grid": "Grade",
    "White": "Branco",
    "Transparent": "Transparente",
    "Spacing": "Espaçamento",
    "⇄ Reverse order": "⇄ Inverter ordem",
    "Combining images…": "Juntando imagens…",
    "Images combined": "Imagens juntadas",
    "No images.": "Nenhuma imagem.",

    # redesign
    "Minimize": "Minimizar",
    "flips": "troca",
    "Look": "Visual", "Native (Windows 11)": "Nativo (Windows 11)", "Liquid glass (classic)": "Vidro líquido (clássico)",
    "Theme": "Tema", "Same as Windows": "Igual ao Windows", "Dark": "Escuro", "Light": "Claro",
    "Arrow": "Seta", "Box": "Caixa", "Circle": "Círculo", "Pen": "Caneta", "Marker": "Marca-texto",
    "Text tool": "Texto", "Step": "Passo", "Flip": "Espelhar", "Delete": "Apagar", "Draw": "Desenhar",
    "From photo": "De uma foto", "Reverse order": "Inverter ordem",
    "Saved next to the original": "Salvo ao lado do original",
    "Saved in a “DragShift” subfolder": "Salvo na subpasta “DragShift”",
    "Compress image": "Comprimir imagem",
    "Compress images": "Comprimir imagens",
    "By quality": "Por qualidade",
    "Maximum size": "Tamanho máximo",
    "Image size": "Tamanho da imagem",

    # unlock
    "Unlock": "Tirar senha",
    "Unlocked": "Sem senha",
    "Remove the password": "Remover a senha",
    "Remove PDF password": "Remover senha do PDF",
    "Type the PDF's current password. A copy without password is saved next to it.":
        "Digite a senha atual do PDF. Uma cópia sem senha é salva ao lado dele.",
    "Remove password": "Remover senha",
    "Wrong password. Try again.": "Senha incorreta. Tente de novo.",
    "Wrong password.": "Senha incorreta.",
    "Removing password…": "Removendo senha…",
    "Password removed": "Senha removida",
    "no password": "sem senha",

    # copy text / OCR
    "Text": "Copiar texto",
    "Copy the text (OCR)": "Copiar o texto (OCR)",
    "Copy text": "Copiar texto",
    "Copy the text inside the selection (Ctrl+Shift+C)": "Copiar o texto da seleção (Ctrl+Shift+C)",
    "Reading…": "Lendo…",
    "Reading text…": "Lendo texto…",
    "Text copied ✓": "Texto copiado ✓",
    "Text copied": "Texto copiado",
    "No text found in this area.": "Nenhum texto encontrado nesta área.",
    "No text found": "Nenhum texto encontrado",
    "No readable text in this image.": "Nenhum texto legível nesta imagem.",
    "Couldn't read the text": "Não foi possível ler o texto",
    "from the PDF": "direto do PDF",
    "recognised (OCR) — check it": "reconhecido por OCR — confira",
    "{n} characters, {src}: “{preview}”": "{n} caracteres, {src}: “{preview}”",
    "{n} characters: “{preview}”": "{n} caracteres: “{preview}”",
    "Text recognition (OCR) needs Windows 10 or 11.": "O reconhecimento de texto (OCR) precisa do Windows 10 ou 11.",
    "The OCR component isn't installed yet. Open DragShift with “Iniciar DragShift.bat” once to install it.":
        "O componente de OCR ainda não está instalado. Abra o DragShift uma vez pelo “Iniciar DragShift.bat” para instalar.",
    "Windows has no OCR language installed. Add one in Settings → Time & language → Language (e.g. Português (Brasil)).":
        "O Windows não tem idioma de OCR instalado. Adicione em Configurações → Hora e idioma → Idioma (ex.: Português (Brasil)).",
}
