# -*- coding: utf-8 -*-

##########################################################################
# Portadas - sermon cover plugin for OpenLP                              #
# ---------------------------------------------------------------------- #
# Copyright (c) 2026 Portadas contributors                               #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
"""
Spanish texts of the plugin (neutral, professional Spanish; the formal "usted" form, no regional vocabulary).

``UI`` holds the texts of the Qt layer, which go through ``openlp.core.common.i18n.translate``:
``{context: {English text: Spanish text}}``. Keep every ``{field}`` and HTML tag of the English text.

``MESSAGES`` holds the plain English texts raised by the domain, application and adapter layers, which know nothing
about Qt, plus template descriptions and icon names. Each ``{}`` in an English key is a value that the code
interpolates (a count, a name, another message); the Spanish text refers to them as ``%1``, ``%2``... in order of
appearance, and may reorder them. Values are localised too, so a field name such as ``main title`` has its own entry.
Technical sanitizer notes appended to a rejection and the words of AI providers are shown as they come.

``tests/test_i18n.py`` fails when code asks for a text that is missing here.
"""

UI = {
    'PortadasPlugin': {
        '<strong>Portadas Plugin</strong><br />Creates sermon cover slides from templates and adds them to the '
        'service.': '<strong>Complemento Portadas</strong><br />Crea portadas de mensajes a partir de plantillas '
                    'y las agrega al orden del servicio.',
        'Add the selected cover to the service.': 'Agregar la portada seleccionada al servicio.',
        'Cover': 'Portada',
        'Covers': 'Portadas',
        'Create a new cover.': 'Crear una portada nueva.',
        'Delete the selected cover.': 'Eliminar la portada seleccionada.',
        'Edit the selected cover.': 'Editar la portada seleccionada.',
        'Preview the selected cover.': 'Previsualizar la portada seleccionada.',
        'Send the selected cover live.': 'Enviar la portada seleccionada a proyección.',
    },
    'PortadasPlugin.Background': {
        'The request failed unexpectedly ({kind}).': 'La solicitud falló de forma inesperada ({kind}).',
    },
    'PortadasPlugin.EditForm': {
        'A cover can have at most {count} readings.': 'Una portada puede tener como máximo {count} lecturas.',
        'A reference must be at most {count} characters.':
            'Una referencia admite como máximo {count} caracteres.',
        'A short subtitle': 'Un subtítulo breve',
        'AI design (optional): describe the style you want': 'Diseño con IA (opcional): describa el estilo que desea',
        'AI design is not available (could not start the designer).':
            'El diseño con IA no está disponible (no se pudo iniciar el diseñador).',
        'AI design is not available in this setup.': 'El diseño con IA no está disponible en esta instalación.',
        'Accent title:': 'Título destacado:',
        'Cancel': 'Cancelar',
        'Cancel design': 'Cancelar diseño',
        'Choose an SVG or PNG file.': 'Elija un archivo SVG o PNG.',
        'Choose an icon': 'Elegir un icono',
        'Cover': 'Portada',
        'Design with AI': 'Diseñar con IA',
        'Designing with the AI. This can take a minute...': 'Diseñando con la IA. Puede tardar un minuto...',
        'Fix the marked fields to see the preview.': 'Corrija los campos marcados para ver la vista previa.',
        'For example: Efesios 6:11-12': 'Por ejemplo: Efesios 6:11-12',
        'For example: Santiago 4:7': 'Por ejemplo: Santiago 4:7',
        'For example: warm colours, a stained-glass feel': 'Por ejemplo: colores cálidos, aire de vitral',
        'Icon rejected': 'Icono rechazado',
        'Icon:': 'Icono:',
        'Icons (*.svg *.png)': 'Iconos (*.svg *.png)',
        'Key verse:': 'Versículo clave:',
        'Label:': 'Etiqueta:',
        'Line {number}: {problem}': 'Línea {number}: {problem}',
        'Main title:': 'Título principal:',
        'Preview up to date.': 'Vista previa actualizada.',
        'Readings (one per line):': 'Lecturas (una por línea):',
        'Readings heading:': 'Encabezado de lecturas:',
        'Rendering the preview...': 'Generando la vista previa...',
        'Sample title': 'Título de ejemplo',
        'Save': 'Guardar',
        'Sends the cover text and your hint to the AI provider you configured. The AI designs the look; it never '
        'writes the text.': 'Envía el texto de la portada y su indicación al proveedor de IA que configuró. La IA '
                            'diseña el aspecto; nunca escribe el texto.',
        'Subtitle:': 'Subtítulo:',
        'Template:': 'Plantilla:',
        'The AI design is ready.': 'El diseño con IA está listo.',
        'The AI design is ready: {notes}': 'El diseño con IA está listo: {notes}',
        'The AI design was cancelled.': 'Se canceló el diseño con IA.',
        'The SVG file is too large.': 'El archivo SVG es demasiado grande.',
        'The cover could not be saved': 'No se pudo guardar la portada',
        'The cover icon is not valid and was replaced by the default icon.':
            'El icono de la portada no es válido y se reemplazó por el icono predeterminado.',
        'The cover is not valid': 'La portada no es válida',
        'The preview appears here.': 'La vista previa aparece aquí.',
        'The preview could not be rendered: {error}': 'No se pudo generar la vista previa: {error}',
        'The saved API key was entered for another server. Enter the key again in Settings > Configure OpenLP > '
        'Covers.':
            'La clave de API guardada se escribió para otro servidor. Escríbala de nuevo en Configuración > '
            'Configurar OpenLP > Portadas.',
        'The saved API key could not be read. Enter it again in Settings > Configure OpenLP > Covers.':
            'No se pudo leer la clave de API guardada. Escríbala de nuevo en Configuración > Configurar OpenLP > '
            'Portadas.',
        'This cover uses an AI-designed template. The text is still exactly what you typed.':
            'Esta portada usa una plantilla diseñada con IA. El texto sigue siendo exactamente el que usted escribió.',
        'This text does not fit; shorten it or choose another template.':
            'Este texto no cabe; acórtelo o elija otra plantilla.',
        'Upload...': 'Cargar...',
        'Uploaded': 'Cargado',
        'Use the selected template instead': 'Usar en su lugar la plantilla seleccionada',
        'Use your own SVG or PNG file as the icon.': 'Use su propio archivo SVG o PNG como icono.',
        'in two colours': 'en dos colores',
    },
    'PortadasPlugin.MediaItem': {
        'Are you sure you want to delete the {count} selected cover(s)? This cannot be undone.':
            '¿Está seguro de que desea eliminar las {count} portadas seleccionadas? Esta acción no se puede '
            'deshacer.',
        'Cover not found': 'Portada no encontrada',
        'Covers': 'Portadas',
        'Delete cover': 'Eliminar portada',
        'Delete covers': 'Eliminar portadas',
        'Edit cover': 'Editar portada',
        'Export PNG': 'Exportar PNG',
        'Export PNG...': 'Exportar PNG...',
        'Filter by title...': 'Filtrar por título...',
        'PNG image (*.png)': 'Imagen PNG (*.png)',
        'Save the selected cover as a PNG image.': 'Guardar la portada seleccionada como imagen PNG.',
        'You must select a cover to delete.': 'Debe seleccionar una portada para eliminar.',
        'You must select a cover to edit.': 'Debe seleccionar una portada para editar.',
        'You must select a cover to export.': 'Debe seleccionar una portada para exportar.',
    },
    'PortadasPlugin.SettingsTab': {
        ' s': ' s',
        'AI cover designs': 'Diseños de portada con IA',
        'API key:': 'Clave de API:',
        'An API key is saved. Type a new one to replace it.':
            'Hay una clave de API guardada. Escriba una nueva para reemplazarla.',
        'An API key is saved. It is only sent to {host}. Type a new one to replace it.':
            'Hay una clave de API guardada. Solo se envía a {host}. Escriba una nueva para reemplazarla.',
        'Anthropic': 'Anthropic',
        'Clear': 'Borrar',
        'Covers settings': 'Configuración de Portadas',
        'Generate AI background images (providers that support it)':
            'Generar imágenes de fondo con IA (proveedores que lo admiten)',
        'Google Gemini': 'Google Gemini',
        'Model:': 'Modelo:',
        'No API key saved.': 'No hay ninguna clave de API guardada.',
        'OpenAI': 'OpenAI',
        'OpenAI-compatible server': 'Servidor compatible con OpenAI',
        'Paste your API key': 'Pegue su clave de API',
        'Provider:': 'Proveedor:',
        'Request timeout:': 'Tiempo máximo de espera:',
        'Server address:': 'Dirección del servidor:',
        'Test connection': 'Probar conexión',
        'Testing {host}...': 'Probando {host}...',
        'Testing...': 'Probando...',
        'The API key was not saved: it is empty, too short or long, or contains spaces or unsupported characters.':
            'No se guardó la clave de API: está vacía, es demasiado corta o larga, o contiene espacios o '
            'caracteres no admitidos.',
        'The saved key is not tied to a server. Enter the key again for {host}.':
            'La clave guardada no está asociada a ningún servidor. Escriba la clave de nuevo para {host}.',
        'The saved key was entered for {saved}. Enter the key again for {host}.':
            'La clave guardada se escribió para {saved}. Escriba la clave de nuevo para {host}.',
        'The saved key will be removed when you press OK.': 'La clave guardada se eliminará al pulsar Aceptar.',
        'The server address was not saved: {error}': 'No se guardó la dirección del servidor: {error}',
        'https://host/v1 or http://localhost:11434/v1': 'https://host/v1 o http://localhost:11434/v1',
    },
}

_RETRY = 'Intente de nuevo más tarde.'
_KEY_CHECK = 'Revise la clave en la configuración de Portadas.'

MESSAGES = {
    # Field names that other messages interpolate.
    'label': 'etiqueta',
    'readings label': 'encabezado de lecturas',
    'main title': 'título principal',
    'accent title': 'título destacado',
    'subtitle': 'subtítulo',
    'verse number': 'número de versículo',
    'chapter number': 'número de capítulo',
    'Key verse': 'Versículo clave',
    'Reading {}': 'Lectura %1',
    '{}: {}': '%1: %2',

    # Template descriptions and icon names.
    'Light, warm cream background with a soft amber glow, dark brown text and bronze accents.':
        'Fondo crema cálido y claro con un suave resplandor ámbar, texto marrón oscuro y detalles en bronce.',
    'Bold monochrome: black background, heavy uppercase sans title, white and grey only.':
        'Monocromo contundente: fondo negro, título en mayúsculas de trazo grueso, solo blanco y gris.',
    'Dark navy background with a soft glow, gold accents and a serif title. Replica of the reference design.':
        'Fondo azul marino oscuro con un suave resplandor, detalles dorados y título con serifa. Réplica del '
        'diseño de referencia.',
    'anchor': 'ancla', 'cross': 'cruz', 'crown': 'corona', 'dove': 'paloma', 'flame': 'llama', 'heart': 'corazón',
    'open bible': 'Biblia abierta', 'praying hands': 'manos en oración', 'shield heart': 'escudo con corazón',
    'star': 'estrella',

    # Cover rules.
    'The {} is required.': 'El campo «%1» es obligatorio.',
    'The "{}" is required.': 'El campo «%1» es obligatorio.',
    'The {} must be at most {} characters.': 'El campo «%1» admite como máximo %2 caracteres.',
    'The {} contains a control or invisible formatting character.':
        'El campo «%1» contiene un carácter de control o de formato invisible.',
    'The {} must be trimmed and free of blank lines or repeated spaces.':
        'El campo «%1» no debe tener espacios al principio o al final, líneas en blanco ni espacios repetidos.',
    '{}: a reference must be at most {} characters.': '%1: una referencia admite como máximo %2 caracteres.',
    'A reference must be at most {} characters.': 'Una referencia admite como máximo %1 caracteres.',
    'A cover can have at most {} readings.': 'Una portada puede tener como máximo %1 lecturas.',
    'The icon kind is not valid.': 'El tipo de icono no es válido.',
    'The icon needs a value.': 'El icono necesita un valor.',
    'The built-in icon name may only use lowercase letters, digits and hyphens.':
        'El nombre del icono incluido solo puede usar letras minúsculas, dígitos y guiones.',
    'The uploaded icon file name is not valid.': 'El nombre del archivo del icono cargado no es válido.',
    'The inline SVG icon must be at most {} characters.': 'El icono SVG incrustado admite como máximo %1 caracteres.',
    'The cover id may only use letters, digits, "-" and "_" (1 to 64 characters).':
        'El identificador de la portada solo puede usar letras, dígitos, "-" y "_" (de 1 a 64 caracteres).',
    'The template id may only use lowercase letters, digits and hyphens.':
        'El identificador de la plantilla solo puede usar letras minúsculas, dígitos y guiones.',
    'The key verse must be a validated reference.': 'El versículo clave debe ser una referencia validada.',
    'The readings must be a tuple of validated references.':
        'Las lecturas deben ser una tupla de referencias validadas.',
    'The icon must be an IconRef.': 'El icono debe ser un IconRef.',
    'The creation time needs a timezone.': 'La hora de creación necesita una zona horaria.',
    'The custom template must be text of at most {} characters.':
        'La plantilla personalizada debe ser un texto de %1 caracteres como máximo.',
    'The icon name may only use lowercase letters, digits and hyphens.':
        'El nombre del icono solo puede usar letras minúsculas, dígitos y guiones.',
    'The icon "{}" is too large.': 'El icono "%1" es demasiado grande.',
    'Unknown icon "{}".': 'Icono desconocido "%1".',

    # Scripture references.
    'The {} must be a positive number.': 'El campo «%1» debe ser un número positivo.',
    'The {} {} is too large.': 'El valor de «%1» (%2) es demasiado grande.',
    'The number "{}" is too large.': 'El número "%1" es demasiado grande.',
    'The reference is empty.': 'La referencia está vacía.',
    'Invalid reference "{}": it must start with a book name.':
        'Referencia no válida "%1": debe comenzar con el nombre de un libro.',
    'Invalid reference "{}": cannot read "{}".': 'Referencia no válida "%1": no se puede leer "%2".',
    'Invalid reference: empty part. Check the "·" and "," separators.':
        'Referencia no válida: hay una parte vacía. Revise los separadores "·" y ",".',
    'Please give a chapter for {}, for example "{} 1:1".': 'Indique un capítulo para %1, por ejemplo "%2 1:1".',
    'Please give a chapter for {}.': 'Indique un capítulo para %1.',
    'Verse {} comes before verse {}; write the range in order.':
        'El versículo %1 va antes que el versículo %2; escriba el rango en orden.',
    'Chapter {} comes before chapter {}; write the range in order.':
        'El capítulo %1 va antes que el capítulo %2; escriba el rango en orden.',
    'A chapter range cannot list verses.': 'Un rango de capítulos no puede indicar versículos.',
    '{} has only {} chapter{}; chapter {} does not exist.': '%1 solo tiene %2 capítulo%3; el capítulo %4 no existe.',
    'Unknown book "{}".': 'Libro desconocido "%1".',
    'Ambiguous book name "{}": it could be {}.': 'Nombre de libro ambiguo "%1": podría ser %2.',
    'Ambiguous book name "{}": please type more letters.': 'Nombre de libro ambiguo "%1": escriba más letras.',

    # Templates.
    'Malformed placeholder: every "{{" must close as a known name followed by "}}".':
        'Marcador mal formado: cada "{{" debe cerrarse con un nombre conocido seguido de "}}".',
    'Malformed placeholder: use exactly two braces, like {{title_main}}.':
        'Marcador mal formado: use exactamente dos llaves, como {{title_main}}.',
    'Unknown placeholder "{}".': 'Marcador desconocido "%1".',
    'The template is missing the required placeholder "{}".': 'A la plantilla le falta el marcador obligatorio "%1".',
    'The manifest "{}" must be a list of placeholder names.':
        'El campo "%1" del manifiesto debe ser una lista de nombres de marcadores.',
    'The manifest is missing {}.': 'Al manifiesto le falta %1.',
    'The manifest has an invalid structure.': 'El manifiesto tiene una estructura no válida.',
    'The manifest id "{}" does not match its folder "{}".':
        'El identificador del manifiesto "%1" no coincide con su carpeta "%2".',
    'The manifest of template "{}" cannot be read.': 'No se puede leer el manifiesto de la plantilla "%1".',
    'The template.html of "{}" cannot be read.': 'No se puede leer el archivo template.html de "%1".',
    'The template needs a name.': 'La plantilla necesita un nombre.',
    'The template description must be text.': 'La descripción de la plantilla debe ser texto.',
    'A template must require at least one placeholder.': 'Una plantilla debe exigir al menos un marcador.',
    'A placeholder cannot be both required and optional.':
        'Un marcador no puede ser obligatorio y opcional a la vez.',
    'The canvas must be {}x{}.': 'El lienzo debe medir %1x%2.',
    'The custom template was rejected: {}': 'Se rechazó la plantilla personalizada: %1',
    'The icon SVG was rejected: {}': 'Se rechazó el SVG del icono: %1',
    'Uploaded icon files are not supported; upload an SVG or PNG instead.':
        'No se admiten archivos de icono cargados de ese tipo; cargue un SVG o PNG.',

    # Cover files and the library.
    'The cover data must be a JSON object.': 'Los datos de la portada deben ser un objeto JSON.',
    'Unsupported cover schema version: {}.': 'Versión de esquema de portada no admitida: %1.',
    'The cover field "{}" must be text.': 'El campo "%1" de la portada debe ser texto.',
    'The cover readings must be a list of text.': 'Las lecturas de la portada deben ser una lista de textos.',
    'The cover icon must be an object with a kind and a value.':
        'El icono de la portada debe ser un objeto con un tipo y un valor.',
    'The cover data is missing "created_at".': 'A los datos de la portada les falta "created_at".',
    'The cover data is missing "{}".': 'A los datos de la portada les falta "%1".',
    'The cover creation time needs a timezone.': 'La hora de creación de la portada necesita una zona horaria.',
    'The cover creation time is not a valid timestamp.': 'La hora de creación de la portada no es válida.',
    'The cover file is not valid JSON.': 'El archivo de la portada no es un JSON válido.',
    'The cover data breaks a rule: {}': 'Los datos de la portada incumplen una regla: %1',
    'Unknown icon kind "{}".': 'Tipo de icono desconocido "%1".',
    'The cover id is not valid.': 'El identificador de la portada no es válido.',
    'There is no cover "{}".': 'No existe la portada "%1".',
    'There is no image for cover "{}".': 'No existe la imagen de la portada "%1".',
    'The cover "{}" is incomplete.': 'La portada "%1" está incompleta.',
    'The cover "{}" cannot be read: it is damaged or unreadable.':
        'No se puede leer la portada "%1": está dañada o es ilegible.',
    'Only covers can be saved.': 'Solo se pueden guardar portadas.',
    'The image is not a PNG.': 'La imagen no es un PNG.',
    'The image is too large.': 'La imagen es demasiado grande.',
    'The cover could not be saved: {}.': 'No se pudo guardar la portada: %1.',
    'The cover could not be deleted: {}.': 'No se pudo eliminar la portada: %1.',
    'The cover could not be exported: {}.': 'No se pudo exportar la portada: %1.',
    'The export destination is a folder.': 'El destino de la exportación es una carpeta.',
    '"{}" already exists.': '"%1" ya existe.',

    # Icon files.
    'The SVG file could not be read as text.': 'No se pudo leer el archivo SVG como texto.',
    'The SVG file is too large (at most {} KB).': 'El archivo SVG es demasiado grande (máximo %1 KB).',
    'The SVG file was rejected: {}': 'Se rechazó el archivo SVG: %1',
    'The file is not a PNG image.': 'El archivo no es una imagen PNG.',
    'The icon must be a regular file.': 'El icono debe ser un archivo normal.',
    'The file could not be read: {}.': 'No se pudo leer el archivo: %1.',
    'The image file is too large.': 'El archivo de imagen es demasiado grande.',
    'The file is not a usable image.': 'El archivo no es una imagen utilizable.',
    'The PNG image is too large (at most {} KB).': 'La imagen PNG es demasiado grande (máximo %1 KB).',
    'The PNG image has unsupported dimensions (at most {} pixels per side).':
        'La imagen PNG tiene dimensiones no admitidas (máximo %1 píxeles por lado).',
    'The PNG image was rejected.': 'Se rechazó la imagen PNG.',
    'The PNG image is damaged (checksum mismatch).': 'La imagen PNG está dañada (la suma de verificación no coincide).',
    'The PNG image has extra data after its end.': 'La imagen PNG tiene datos adicionales después de su final.',
    'The PNG image is incomplete.': 'La imagen PNG está incompleta.',

    # Settings and API keys.
    'The server address is empty.': 'La dirección del servidor está vacía.',
    'The server address is not valid.': 'La dirección del servidor no es válida.',
    'The server address is not valid: {}': 'La dirección del servidor no es válida: %1',
    'The server address must start with https:// (or http://localhost for a local server).':
        'La dirección del servidor debe comenzar con https:// (o http://localhost para un servidor local).',
    'The server address must not contain a user name or password.':
        'La dirección del servidor no debe contener un usuario ni una contraseña.',
    'The server address must not contain a query or a fragment.':
        'La dirección del servidor no debe contener una consulta ni un fragmento.',
    'Plain http:// is only allowed for localhost or 127.0.0.1. Use https:// otherwise.':
        'http:// sin cifrar solo se permite para localhost o 127.0.0.1. En los demás casos use https://.',
    'The API key is empty, too short or long, or contains spaces or unsupported characters.':
        'La clave de API está vacía, es demasiado corta o larga, o contiene espacios o caracteres no admitidos.',
    'The API key for {} contains spaces or unsupported characters.':
        'La clave de API de %1 contiene espacios o caracteres no admitidos.',
    'No API key is saved for {}. Add one in Settings > Configure OpenLP > Covers.':
        'No hay ninguna clave de API guardada para %1. Agregue una en Configuración > Configurar OpenLP > Portadas.',
    'The API key could not be saved. Check the permissions of the OpenLP data folder.':
        'No se pudo guardar la clave de API. Revise los permisos de la carpeta de datos de OpenLP.',
    'The API keys are being changed by another OpenLP window. Try again in a moment.':
        'Otra ventana de OpenLP está modificando las claves de API. Intente de nuevo en unos instantes.',
    'The stored API keys could not be inspected.': 'No se pudieron examinar las claves de API guardadas.',
    'The stored API keys cannot be trusted or read and could not be backed up.':
        'Las claves de API guardadas no son fiables ni legibles, y no se pudo hacer una copia de seguridad.',
    'The folder for the API keys is a symbolic link, which is not accepted.':
        'La carpeta de las claves de API es un enlace simbólico, que no se acepta.',
    'Windows could not protect or unprotect the stored API keys.':
        'Windows no pudo proteger ni desproteger las claves de API guardadas.',

    # AI designs.
    'The AI provider is not supported.': 'El proveedor de IA no es compatible.',
    'The AI settings are missing.': 'Faltan los ajustes de IA.',
    'This provider cannot be tested.': 'Este proveedor no se puede probar.',
    'The model name is not valid. Use letters, digits and . _ - only.':
        'El nombre del modelo no es válido. Use solo letras, dígitos y . _ -',
    'The model name is not valid. Use letters, digits and . _ : / @ + - only.':
        'El nombre del modelo no es válido. Use solo letras, dígitos y . _ : / @ + -',
    'The request was cancelled.': 'Se canceló la solicitud.',
    'The answer of the AI provider is too large and was discarded.':
        'La respuesta del proveedor de IA es demasiado grande y se descartó.',
    'The answer of {} was interrupted.': 'La respuesta de %1 se interrumpió.',
    'A secure connection to {} could not be made.': 'No se pudo establecer una conexión segura con %1.',
    'Could not connect to {}. Check your internet connection and the server address.':
        'No se pudo conectar con %1. Revise su conexión a internet y la dirección del servidor.',
    'The request to {} failed.': 'La solicitud a %1 falló.',
    '{} did not answer.': '%1 no respondió.',
    '{} did not answer in time. Try again, or raise the request timeout in the Covers settings.':
        '%1 no respondió a tiempo. Intente de nuevo o aumente el tiempo máximo de espera en la configuración de '
        'Portadas.',
    '{} rejected the API key (HTTP {}). Check the key in the Covers settings.':
        '%1 rechazó la clave de API (HTTP %2). ' + _KEY_CHECK,
    '{} said that the model or address was not found (HTTP 404). Check the model name.':
        '%1 indicó que no encontró el modelo o la dirección (HTTP 404). Revise el nombre del modelo.',
    '{} rejected the request (HTTP 400).': '%1 rechazó la solicitud (HTTP 400).',
    '{} is limiting requests or the quota is used up (HTTP 429). Try again later.':
        '%1 está limitando las solicitudes o se agotó la cuota (HTTP 429). ' + _RETRY,
    '{} answered with a redirect (HTTP {}), which is not followed. Check the server address.':
        '%1 respondió con una redirección (HTTP %2), que no se sigue. Revise la dirección del servidor.',
    '{} is unavailable right now (HTTP {}). Try again later.': '%1 no está disponible en este momento (HTTP %2). '
                                                              + _RETRY,
    '{} answered with an error (HTTP {}).': '%1 respondió con un error (HTTP %2).',
    '{} sent an unexpected answer (it is not a JSON object).':
        '%1 envió una respuesta inesperada (no es un objeto JSON).',
    '{} sent an unexpected answer (no candidates).': '%1 envió una respuesta inesperada (sin candidatos).',
    '{} sent an unexpected answer (no choices).': '%1 envió una respuesta inesperada (sin opciones).',
    '{} sent an unexpected answer (no content).': '%1 envió una respuesta inesperada (sin contenido).',
    '{} blocked the request ({}).': '%1 bloqueó la solicitud (%2).',
    '{} refused to design this cover.': '%1 se negó a diseñar esta portada.',
    'The reply was empty.': 'La respuesta estaba vacía.',
    '{} The AI answered, but without a design.': '%1 La IA respondió, pero sin ningún diseño.',
    'The AI reply is too long.': 'La respuesta de la IA es demasiado larga.',
    'The AI answered with an empty reply.': 'La IA respondió con una respuesta vacía.',
    'The AI provider returned an unusable answer.': 'El proveedor de IA devolvió una respuesta inutilizable.',
    'The AI reply is not valid JSON.': 'La respuesta de la IA no es un JSON válido.',
    'The AI reply is not valid JSON with an "html" template.':
        'La respuesta de la IA no es un JSON válido con una plantilla "html".',
    'The AI reply is not valid JSON: "icon_svg" must be text or null.':
        'La respuesta de la IA no es un JSON válido: "icon_svg" debe ser texto o null.',
    'The AI reply was cut off before the JSON was complete; try again or choose a model with a larger output limit.':
        'La respuesta de la IA se cortó antes de completar el JSON; intente de nuevo o elija un modelo con un '
        'límite de salida mayor.',
    'The AI design could not be made safe after one correction ({}). Try again or change the style hint.':
        'No se pudo hacer seguro el diseño de la IA tras una corrección (%1). Intente de nuevo o cambie la '
        'indicación de estilo.',
}
