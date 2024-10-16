// Translate
const translate_div = $('#translate');
const cancel_word = translate_div.attr('data-cancel');
let add_word = translate_div.attr('data-add');
const close_word = translate_div.attr('data-close');
const save_word = translate_div.attr('data-save');
const edit_word = translate_div.attr('data-edit');
const delete_word = translate_div.attr('data-delete');
const back_word = translate_div.attr('data-back');
const resp_time_word = translate_div.attr('data-resp_time');

// JS scripts URL
const scriptPath = "/static/js"
const script = `${scriptPath}/script.js`;
const overview = `${scriptPath}/overview.js`;
const awesome = `${scriptPath}/fontawesome.min.js`;

// csrf_token
const csrf_token = Cookies.get('csrf_access_token');

// Current API version prefix
const api_v_prefix = '/api/v1.0'

// Check types
const check_types = {'tcp': 1, 'http': 2, 'smtp': 3, 'ping': 4, 'dns': 5, 'rabbitmq': 6};
const check_types_id = {1: 'tcp', 2: 'http', 3: 'smtp', 4: 'ping', 5: 'dns', 6: 'rabbitmq'};
