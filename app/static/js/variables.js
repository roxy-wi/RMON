// Translate
const translate_div = $('#translate');
const cancel_word = translate_div.attr('data-cancel');
let add_word = translate_div.attr('data-add');
const close_word = translate_div.attr('data-close');
const service_word = translate_div.attr('data-service');
const save_word = translate_div.attr('data-save');
const just_save_word = translate_div.attr('data-just_save');
const upload_and_reload = translate_div.attr('data-upload_and_reload');
const upload_and_restart = translate_div.attr('data-upload_and_restart');
const edit_word = translate_div.attr('data-edit');
const delete_word = translate_div.attr('data-delete');
const back_word = translate_div.attr('data-back');
const resp_time_word = translate_div.attr('data-resp_time');

// JS scripts URL
const scriptPath = "/static/js"
const script = `${scriptPath}/script.js`;
const overview = `${scriptPath}/overview.js`;
const awesome = `${scriptPath}/fontawesome.min.js`;
const ha = `${scriptPath}/ha.js`;

// csrf_token
const csrf_token = Cookies.get('csrf_access_token');

// Current API version prefix
const api_v_prefix = '/api/v1.0'
