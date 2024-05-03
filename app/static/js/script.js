var url = "/static/js/script.js";
var cur_url = window.location.href.split('/');
var intervalId;
function validateEmail(email) {
	const re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
	return re.test(email);
}
function ValidateIPaddress(ipaddress) {
	if (/^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/.test(ipaddress)) {
		return (true)
	}
	return (false)
}
function escapeHtml(unsafe) {
	return unsafe
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#039;");
}
var wait_mess_word = $('#translate').attr('data-wait_mess');
var wait_mess = '<div class="alert alert-warning">'+wait_mess_word+'</div>'
function show_current_page(id) {
	id.parent().css('display', 'contents');
	id.parent().css('font-size', '13px');
	id.parent().css('top', '0');
	id.parent().css('left', '0');
	id.parent().children().css('margin-left', '-20px');
	id.parent().find('a').css('padding-left', '20px');
	id.find('a').css('background-color', 'var(--right-menu-blue-color)');
}
$( function() {		
   $('.menu li ul li').each(function () {
	   var link = $(this).find('a').attr('href').split('/').pop();
	   var link2 = link.split('#')[0];
	   var link3 = link.split('#')[1];
	   var full_uri1 = link2 + '#' + link3
	   if (cur_url == full_uri1) {
		   show_current_page($(this));
	   }
   });
});

jQuery.expr[':'].regex = function(elem, index, match) {
    var matchParams = match[3].split(','),
        validLabels = /^(data|css):/,
        attr = {
            method: matchParams[0].match(validLabels) ?
                        matchParams[0].split(':')[0] : 'attr',
            property: matchParams.shift().replace(validLabels,'')
        },
        regexFlags = 'ig',
        regex = new RegExp(matchParams.join('').replace(/^\s+|\s+$/g,''), regexFlags);
    return regex.test(jQuery(elem)[attr.method](attr.property));
}
window.onblur= function() {
	window.onfocus= function () {
		if(sessionStorage.getItem('auto-refresh-pause') == "0" && sessionStorage.getItem('auto-refresh') > 5000) {
			if (cur_url[0] == "logs") {
				showLog();
			} else if (cur_url[0] == "/") {
				showOverview();
			} else if (cur_url[0] == "internal") {
				viewLogs();
			} else if (cur_url[3] == "rmon" && cur_url[4] == "dashboard" && !cur_url[5]) {
				showSmon('refresh');
			} else if (cur_url[3] == "rmon" && cur_url[4] == "dashboard" && cur_url[5]) {
				showSmonHistory();
			}
		}
	}
};
$( document ).ajaxSend(function( event, request, settings ) {
	NProgress.start();
});
$( document ).ajaxComplete(function( event, request, settings ) {
	NProgress.done();
});
function showLog() {
	var waf = cur_url[2];
	var file = $('#log_files').val();
	var serv = $("#serv").val();
	if ((file === undefined || file === null) && (waf == '' || waf === undefined)) {
		var file_from_get = findGetParameter('file');
		if (file_from_get === undefined || file_from_get === null) {
			toastr.warning('Select a log file first')
			return false;
		} else {
			file = file_from_get;
		}
	}
	var rows = $('#rows').val();
	var grep = $('#grep').val();
	var exgrep = $('#exgrep').val();
	var hour = $('#time_range_out_hour').val();
	var minute = $('#time_range_out_minut').val();
	var hour1 = $('#time_range_out_hour1').val();
	var minute1 = $('#time_range_out_minut1').val();
	var service = $('#service').val();
	if (service == 'None') {
		service = 'haproxy';
	}
	if (waf) {
		var url = "/logs/" + service + "/waf/" + serv + "/" + rows;
		waf = 1;
	} else {
		var url = "/logs/" + service + "/" + serv + "/" + rows;
	}
	$.ajax( {
		url: url,
		data: {
			show_log: rows,
			waf: waf,
			grep: grep,
			exgrep: exgrep,
			hour: hour,
			minute: minute,
			hour1: hour1,
			minute1: minute1,
			file: file,
			token: $('#token').val()
		},
		type: "POST",
		success: function( data ) {
			toastr.clear();
			$("#ajax").html(data);
		}
	} );
}
function showRemoteLogFiles() {
	let serv = $('#serv').val();
	if (serv === undefined || serv === null) {
		toastr.warning('Select a server firts');
		return false;
	}
	var rows = $('#rows').val()
	var grep = $('#grep').val()
	var exgrep = $('#exgrep').val()
	var hour = $('#time_range_out_hour').val()
	var minute = $('#time_range_out_minut').val()
	var hour1 = $('#time_range_out_hour1').val()
	var minute1 = $('#time_range_out_minut1').val()
	var service = $('#service').val()
	if (service == 'None') {
		service = 'haproxy';
	}
	$.ajax( {
		url: "/logs/" + service + "/" + serv ,
		data: {
			serv: $("#serv").val(),
			token: $('#token').val()
		},
		type: "POST",
		success: function( data ) {
			if (data.indexOf('error:') != '-1' || data.indexOf('ls: cannot access') != '-1') {
				toastr.error(data);
			} else {
				toastr.clear();
				$("#remote_log_files").html(data);
				$.getScript('/static/js/configshow.js');
			}
		}
	} );

}
function clearAllAjaxFields() {
	$("#ajax").empty();
	$('.alert').remove();
	try {
		myCodeMirror.toTextArea();
	} catch (e) {
		console.log(e)
	}
	$("#saveconfig").remove();
	$("h4").remove();
	$("#ajax-compare").empty();
	$("#config").empty();
}
function findGetParameter(parameterName) {
    var result = null,
        tmp = [];
    var items = location.search.substr(1).split("&");
    for (var index = 0; index < items.length; index++) {
        tmp = items[index].split("=");
        if (tmp[0] === parameterName) result = decodeURIComponent(tmp[1]);
    }
    return result;
}
function viewLogs() {
	var viewlogs = $('#viewlogs').val();
	if (viewlogs == '------' || viewlogs === null) { return false; }
	if(viewlogs == 'rmon.error.log' || viewlogs == 'rmon.access.log' || viewlogs == 'fail2ban.log') {
		showApacheLog(viewlogs);
	} else {
		var rows = $('#rows').val();
		var grep = $('#grep').val();
		var exgrep = $('#exgrep').val();
		var hour = $('#time_range_out_hour').val();
		var minute = $('#time_range_out_minut').val();
		var hour1 = $('#time_range_out_hour1').val();
		var minute1 = $('#time_range_out_minut1').val();
		var type = findGetParameter('type')
		if (viewlogs == null){
			viewlogs = findGetParameter('viewlogs')
		}
		var url = "/logs/internal/" + viewlogs + "/" + rows;
		$.ajax({
			url: url,
			data: {
				viewlogs: viewlogs,
				serv: viewlogs,
				rows: rows,
				grep: grep,
				exgrep: exgrep,
				hour: hour,
				minute: minute,
				hour1: hour1,
				minute1: minute1,
				token: $('#token').val(),
			},
			type: "POST",
			success: function (data) {
				$("#ajax").html(data);
			}
		} );
	}
}
$( function() {
	$('a').click(function (e) {
		try {
			var cur_path = window.location.pathname;
			var attr = $(this).attr('href');
			if (cur_path == '/add/haproxy' || cur_path == '/add/nginx' || cur_path == '/servers' ||
				cur_path == '/admin' || cur_path == '/install' || cur_path == '/runtimeapi') {
				if (typeof attr !== typeof undefined && attr !== false) {
					$('title').text($(this).attr('title'));
					history.pushState({}, '', $(this).attr('href'));
					if ($(this).attr('href').split('#')[0] && $(this).attr('href').split('#')[0] != cur_path) {
						window.history.go()
					}
				}
			}
		} catch (err) {
			console.log(err);
		}
	});
	toastr.options.closeButton = true;
	toastr.options.progressBar = true;
	toastr.options.positionClass = 'toast-bottom-full-width';
	toastr.options.timeOut = 25000;
	toastr.options.extendedTimeOut = 50000;
	$('#errorMess').click(function () {
		$('#error').remove();
	});
	$("#serv").on('selectmenuchange', function () {
		$("#show").css("pointer-events", "inherit");
		$("#show").css("cursor", "pointer");
	});
	if ($("#serv option:selected").val() == "Choose server") {
		$("#show").css("pointer-events", "none");
		$("#show").css("cursor", "not-allowed");
	}
	$("#tabs").tabs();
	$("select").selectmenu();

	$("[title]").tooltip({
		"content": function () {
			return $(this).attr("data-help");
		},
		show: {"delay": 1000}
	});
	$("input[type=submit], button").button();
	$("input[type=checkbox]").checkboxradio();
	$(".controlgroup").controlgroup();

	$("#hide_menu").click(function () {
		$(".top-menu").hide("drop", "fast");
		$(".container").css("max-width", "100%");
		$(".footer").css("max-width", "97%");
		$(".container").css("margin-left", "1%");
		$(".footer").css("margin-left", "1%");
		$(".show_menu").show();
		$("#hide_menu").hide();
		sessionStorage.setItem('hide_menu', 'hide');
	});
	$("#show_menu").click(function () {
		$(".top-menu").show("drop", "fast");
		$(".container").css("max-width", "100%");
		$(".footer").css("max-width", "100%");
		$(".container").css("margin-left", "207px");
		$(".footer").css("margin-left", "207px");
		$(".show_menu").hide();
		$("#hide_menu").show();
		sessionStorage.setItem('hide_menu', 'show');
	});
	var hideMenu = sessionStorage.getItem('hide_menu');
	if (hideMenu == "show") {
		$(".top-menu").show("drop", "fast");
		$(".container").css("max-width", "100%");
		$(".container").css("margin-left", "207px");
		$(".footer").css("margin-left", "207px");
		$(".footer").css("max-width", "100%");
		$("#hide_menu").show();
		$(".show_menu").hide();
	}
	if (hideMenu == "hide") {
		$(".top-menu").hide();
		$(".container").css("max-width", "97%");
		$(".container").css("margin-left", "1%");
		$(".footer").css("margin-left", "1%");
		$(".footer").css("max-width", "97%");
		$(".show_menu").show();
		$("#hide_menu").hide();
	}

	var now = new Date(Date.now());
	if ($('#time_range_out_hour').val() != '' && $('#time_range_out_hour').val() != 'None') {
		var date1 = parseInt($('#time_range_out_hour').val(), 10) * 60 + parseInt($('#time_range_out_minut').val(), 10)
	} else {
		var date1 = now.getHours() * 60 - 3 * 60;
	}
	if ($('#time_range_out_hour').val() != '' && $('#time_range_out_hour').val() != 'None') {
		var date2 = parseInt($('#time_range_out_hour1').val(), 10) * 60 + parseInt($('#time_range_out_minut1').val(), 10)
	} else {
		var date2 = now.getHours() * 60 + now.getMinutes();
	}
	$("#time-range").slider({
		range: true,
		min: 0,
		max: 1440,
		step: 15,
		values: [date1, date2],
		slide: function (e, ui) {
			var hours = Math.floor(ui.values[0] / 60);
			var minutes = ui.values[0] - (hours * 60);

			if (hours.toString().length == 1) hours = '0' + hours;
			if (minutes.toString().length == 1) minutes = '0' + minutes;

			var hours1 = Math.floor(ui.values[1] / 60);
			var minutes1 = ui.values[1] - (hours1 * 60);

			if (hours1.toString().length == 1) hours1 = '0' + hours1;
			if (minutes1.toString().length == 1) minutes1 = '0' + minutes1;
			if ($('#time_range_out_hour').val() != '' && $('#time_range_out_hour').val() != 'None') {
				$('#time_range_out_hour').val(hours);
			}
			if ($('#time_range_out_minut').val() != '' && $('#time_range_out_minut').val() != 'None') {
				$('#time_range_out_minut').val(minutes);
			}
			if ($('#time_range_out_hour1').val() != '' && $('#time_range_out_hour1').val() != 'None') {
				$('#time_range_out_hour1').val(hours1);
			}
			if ($('#time_range_out_minut1').val() != '' && $('#time_range_out_minut1').val() != 'None') {
				$('#time_range_out_minut1').val(minutes1);
			}
		}
	});
	var date1_hours = Math.floor(date1 / 60);
	var date2_hours = date1_hours + 1;
	var date2_minute = now.getMinutes()
	if (date1_hours <= 9) date1_hours = '0' + date1_hours;
	if (date2_hours <= 9) date2_hours = '0' + date2_hours;
	if (date2_minute <= 9) date2_minute = '0' + date2_minute;
	if ($('#time_range_out_hour').val() != '' && $('#time_range_out_hour').val() != 'None') {
		$('#time_range_out_hour').val($('#time_range_out_hour').val());
	} else {
		$('#time_range_out_hour').val(date1_hours);
	}
	if ($('#time_range_out_minut').val() != '' && $('#time_range_out_minut').val() != 'None') {
		$('#time_range_out_minut').val($('#time_range_out_minut').val());
	} else {
		$('#time_range_out_minut').val('00');
	}
	if ($('#time_range_out_hour1').val() != '' && $('#time_range_out_hour1').val() != 'None') {
		$('#time_range_out_hour1').val($('#time_range_out_hour1').val());
	} else {
		$('#time_range_out_hour1').val(date2_hours);
	}
	if ($('#time_range_out_minut1').val() != '' && $('#time_range_out_minut1').val() != 'None') {
		$('#time_range_out_minut1').val($('#time_range_out_minut1').val());
	} else {
		$('#time_range_out_minut1').val(date2_minute);
	}

	$('#0').click(function () {
		$('.auto-refresh-div').show("blind", "fast");
		$('#0').css("display", "none");
		$('#1').css("display", "inline");
	});

	$('#1').click(function () {
		$('.auto-refresh-div').hide("blind", "fast");
		$('#1').css("display", "none");
		$('#0').css("display", "inline");
	});
	$('#auth').submit(function () {
		var next_url = findGetParameter('next');
		$.ajax({
			url: "/login",
			data: {
				login: $('#login').val(),
				pass: $('#pass').val(),
				next: next_url
			},
			type: "POST",
			success: function (data) {
				if (data.indexOf('disabled') != '-1') {
					$('.alert').show();
					$('.alert').html(data);
				} else if (data.indexOf('ban') != '-1') {
					ban();
				} else if (data.indexOf('error') != '-1') {
					toastr.error(data);
				} else {
					sessionStorage.removeItem('check-service');
					window.location.replace(data);
				}
			}
		});
		return false;
	});
	$('#show_log_form').submit(function () {
		showLog();
		return false;
	});
	$('#show_internal_log_form').submit(function () {
		viewLogs();
		return false;
	});

	var user_settings_tabel_title = $("#show-user-settings-table").attr('title');
	var cancel_word = $('#translate').attr('data-cancel');
	var save_word = $('#translate').attr('data-save');
	var change_word = $('#translate').attr('data-change');
	var password_word = $('#translate').attr('data-password');
	var change_pass_word = change_word + ' ' + password_word
	var showUserSettings = $("#show-user-settings").dialog({
		autoOpen: false,
		width: 600,
		modal: true,
		title: user_settings_tabel_title,
		buttons: [{
			text: save_word,
			click: function () {
				saveUserSettings();
				$(this).dialog("close");
			}
		}, {
			text: change_pass_word,
			click: function () {
				changePassword();
				$(this).dialog("close");
			}
		}, {
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
			}
		}]
	});

	$('#show-user-settings-button').click(function () {
		if (localStorage.getItem('disabled_alert') == '1') {
			$('#disable_alerting').prop('checked', false).checkboxradio('refresh');
		} else {
			$('#disable_alerting').prop('checked', true).checkboxradio('refresh');
		}
		let theme = 'light';
		if(localStorage.getItem('theme') != null) {
			theme = localStorage.getItem('theme');
		}
		$('#theme_select').val(theme).change();
		$('#theme_select').selectmenu('refresh');
		$.ajax({
			url: "/user/group/current",
			success: function (data) {
				if (data.indexOf('danger') != '-1') {
					$("#ajax").html(data);
				} else {
					$('#show-user-settings-group').html(data);
					$("select").selectmenu();
				}
			}
		});
		showUserSettings.dialog('open');
	});
	var cur_url = window.location.href.split('/').pop();
	cur_url = cur_url.split('/');
	cur_url = cur_url[0].split('#');
	if (cur_url[0].indexOf('admin') != '-1' || cur_url[0].indexOf('servers') != '-1') {
		$(".users").on("click", function () {
			$('.menu li ul li').each(function () {
				$(this).find('a').css('padding-left', '20px')
				$(this).find('a').css('border-left', '0px solid var(--right-menu-blue-color)');
				$(this).find('a').css('background-color', 'var(--color-blue-light)');
				$(this).children(".users").css('padding-left', '30px');
				$(this).children(".users").css('border-left', '4px solid var(--right-menu-blue-color)');
				$(this).children(".users").css('background-color', 'var(--right-menu-blue-color)');
			});
			$("#tabs").tabs("option", "active", 0);
		});
		$(".runtime-menu").on("click", function () {
			$('.menu li ul li').each(function () {
				$(this).find('a').css('border-left', '0px solid var(--right-menu-blue-color)');
				$(this).find('a').css('padding-left', '20px');
				$(this).find('a').css('background-color', 'var(--color-blue-light)');
				$(this).children(".runtime-menu").css('padding-left', '30px');
				$(this).children(".runtime-menu").css('border-left', '4px solid var(--right-menu-blue-color)');
				$(this).children(".runtime-menu").css('background-color', 'var(--right-menu-blue-color)');
			});
			$("#tabs").tabs("option", "active", 1);
		});
		$(".admin-menu").on("click", function () {
			$('.menu li ul li').each(function () {
				$(this).find('a').css('padding-left', '20px');
				$(this).find('a').css('border-left', '0px solid var(--right-menu-blue-color)');
				$(this).find('a').css('background-color', 'var(--color-blue-light)');
				$(this).children(".admin-menu").css('padding-left', '30px');
				$(this).children(".admin-menu").css('border-left', '4px solid var(--right-menu-blue-color)');
				$(this).children(".admin-menu").css('background-color', 'var(--right-menu-blue-color)');
			});
			$("#tabs").tabs("option", "active", 2);
		});
		$(".settings").on("click", function () {
			$('.menu li ul li').each(function () {
				$(this).find('a').css('border-left', '0px solid var(--right-menu-blue-color)');
				$(this).find('a').css('padding-left', '20px');
				$(this).find('a').css('background-color', 'var(--color-blue-light)');
				$(this).children(".settings").css('padding-left', '30px');
				$(this).children(".settings").css('border-left', '4px solid var(--right-menu-blue-color)');
				$(this).children(".settings").css('background-color', 'var(--right-menu-blue-color)');
			});
			$("#tabs").tabs("option", "active", 3);
		});
		$(".group").on("click", function () {
			$('.menu li ul li').each(function () {
				$(this).find('a').css('padding-left', '20px');
				$(this).find('a').css('border-left', '0px solid var(--right-menu-blue-color)');
				$(this).find('a').css('background-color', 'var(--color-blue-light)');
				$(this).children(".group").css('padding-left', '30px');
				$(this).children(".group").css('border-left', '4px solid var(--right-menu-blue-color)');
				$(this).children(".group").css('background-color', 'var(--right-menu-blue-color)');
			});
			$("#tabs").tabs("option", "active", 4);
		});
		$(".tools").on("click", function () {
			$('.menu li ul li').each(function () {
				$(this).find('a').css('border-left', '0px solid var(--right-menu-blue-color)');
				$(this).find('a').css('padding-left', '20px');
				$(this).find('a').css('background-color', 'var(--color-blue-light)');
				$(this).children(".tools").css('padding-left', '30px');
				$(this).children(".tools").css('border-left', '4px solid var(--right-menu-blue-color)');
				$(this).children(".tools").css('background-color', 'var(--right-menu-blue-color)');
			});
			$("#tabs").tabs("option", "active", 5);
			loadServices();
		});
		$(".updatehapwi").on("click", function () {
			$('.menu li ul li').each(function () {
				$(this).find('a').css('border-left', '0px solid var(--right-menu-blue-color)');
				$(this).find('a').css('padding-left', '20px');
				$(this).find('a').css('background-color', 'var(--color-blue-light)');
				$(this).children(".updatehapwi").css('padding-left', '30px');
				$(this).children(".updatehapwi").css('border-left', '4px solid var(--right-menu-blue-color)');
				$(this).children(".updatehapwi").css('background-color', 'var(--right-menu-blue-color)');
			});
			$("#tabs").tabs("option", "active", 6);
			loadupdatehapwi();
		});
	}
	$('.copyToClipboard').hover(function () {
		$.getScript("/static/js/fontawesome.min.js");
	});
	$('.copyToClipboard').click(function () {
		let str = $(this).attr('data-copy');
		const el = document.createElement('textarea');
		el.value = str;
		el.setAttribute('readonly', '');
		el.style.position = 'absolute';
		el.style.left = '-9999px';
		document.body.appendChild(el);
		el.select();
		document.execCommand('copy');
		document.body.removeChild(el);
	})
});
function saveUserSettings(){
	if ($('#disable_alerting').is(':checked')) {
		localStorage.removeItem('disabled_alert');
	} else {
		localStorage.setItem('disabled_alert', '1');
	}
	changeCurrentGroupF();
	changeTheme($('#theme_select').val());
	Cookies.set('lang', $('#lang_select').val(), { expires: 365, path: '/', samesite: 'strict', secure: 'true' });
}
function sleep(ms) {
	return new Promise(resolve => setTimeout(resolve, ms));
}
function changeTheme(theme) {
	localStorage.setItem('theme', theme);
	if (theme === 'dark') {
		$('head').append('<link rel="stylesheet" href="/static/css/dark.css" type="text/css" />');
	} else {
		$('link[rel=stylesheet][href~="/static/css/dark.css"]').remove();
	}
}
function checkTheme() {
	let theme = localStorage.getItem('theme');
	changeTheme(theme);
}
checkTheme();
async function ban() {
	$( '#login').attr('disabled', 'disabled');
	$( '#pass').attr('disabled', 'disabled');
	$( "input[type=submit], button" ).button('disable');
	$('#wrong-login').show();
	$('#ban_10').show();
	$( '#ban_timer').text(10);

	let i = 10;
	while (i > 0) {
		i--;
		await sleep(1000);
		$( '#ban_timer').text(i);
		}

	$( '#login').removeAttr('disabled');
	$( '#pass').removeAttr('disabled');
	$( "input[type=submit], button" ).button('enable');
	$('#ban_10').hide();
}
function replace_text(id_textarea, text_var) {
	var str = $(id_textarea).val();
	var len = str.length;
	var len_var = text_var.length;
	var beg = str.indexOf(text_var);
	var end = beg + len_var
	var text_val = str.substring(0, beg) + str.substring(end, len);
	$(id_textarea).text(text_val);
}
function createHistory() {
	if(localStorage.getItem('history') === null) {
		var get_history_array = ['login', 'login','login'];
		localStorage.setItem('history', JSON.stringify(get_history_array));
	}
}
function listHistory() {
	var browse_history = JSON.parse(localStorage.getItem('history'));
	var history_link = '';
	var title = []
	var link_text = []
	var cur_path = window.location.pathname;
	for(let i = 0; i < browse_history.length; i++){
		if (i == 0) {
			browse_history[0] = browse_history[1];
		}
		if (i == 1) {
			browse_history[1] = browse_history[2]
		}
		if (i == 2) {
			browse_history[2] = cur_path
		}
		$( function() {
			$('.menu li ul li').each(function () {
				var link1 = $(this).find('a').attr('href');
				if (browse_history[i].replace(/\/$/, "") == link1) {
					title[i] = $(this).find('a').attr('title');
					link_text[i] = $(this).find('a').text();
					history_link = '<li><a href="'+browse_history[i]+'" title="'+title[i]+'">'+link_text[i]+'</a></li>'
					$('#browse_history').append(history_link);
				}
			});
		});
	}
	localStorage.setItem('history', JSON.stringify(browse_history));
}
createHistory();
listHistory();

function changeCurrentGroupF() {
	Cookies.remove('group');
	Cookies.set('group', $('#newCurrentGroup').val(), {expires: 365, path: '/', samesite: 'strict', secure: 'true'});
	$.ajax({
		url: "/user/group/change",
		data: {
			changeUserCurrentGroupId: $('#newCurrentGroup').val(),
			changeUserGroupsUser: Cookies.get('uuid'),
			token: $('#token').val()
		},
		type: "POST",
		success: function (data) {
			if (data.indexOf('error: ') != '-1') {
				toastr.error(data);
			} else {
				toastr.clear();
				location.reload();
			}
		}
	});
}
function updateTips( t ) {
	var tips = $( ".validateTips" );
	tips.text( t ).addClass( "alert-warning" );
	tips.text( t ).addClass( "alert-one-row" );
}
function clearTips() {
	var tips = $( ".validateTips" );
	tips.html('Fields marked "<span class="need-field">*</span>" are required').removeClass( "alert-warning" );
	allFields = $( [] ).add( $('#new-server-add') ).add( $('#new-ip') ).add( $('#new-port')).add( $('#new-username') ).add( $('#new-password') )
	allFields.removeClass( "ui-state-error" );
}
function checkLength( o, n, min ) {
	if ( o.val().length < min ) {
		o.addClass( "ui-state-error" );
		updateTips("Field "+n+" is required");
		return false;
	} else {
		return true;
	}
}
$(function () {
	ion.sound({
		sounds: [
			{
				name: "bell_ring",
			},
			{
				name: "glass",
				volume: 1,
			},
			{
				name: "alert_sound",
				volume: 0.3,
				preload: false
			}
		],
		volume: 0.5,
		path: "/static/js/sounds/",
		preload: true
	});
});
let socket = new ReconnectingWebSocket("wss://" + window.location.host, null, {maxReconnectAttempts: 20, reconnectInterval: 3000});

socket.onopen = function(e) {
  console.log("[open] Connection is established with " + window.location.host);
  getAlerts();
};

function getAlerts() {
	socket.send("alert_group " + Cookies.get('group') + ' ' + Cookies.get('uuid'));
}

socket.onmessage = function(event) {
	var cur_url = window.location.href.split('/').pop();
	cur_url = cur_url.split('/');
	if (cur_url != 'login' && localStorage.getItem('disabled_alert') === null) {
		data = event.data.split(";");
		for (i = 0; i < data.length; i++) {
			if (data[i].indexOf('error:') != '-1' || data[i].indexOf('alert') != '-1' || data[i].indexOf('FAILED') != '-1') {
				if (data[i].indexOf('error: database is locked') == '-1') {
					toastr.error(data[i]);
					ion.sound.play("bell_ring");
				}
			} else if (data[i].indexOf('info: ') != '-1') {
				toastr.info(data[i]);
				ion.sound.play("glass");
			} else if (data[i].indexOf('success: ') != '-1') {
				toastr.success(data[i]);
				ion.sound.play("glass");
			} else if (data[i].indexOf('warning: ') != '-1') {
				toastr.warning(data[i]);
				ion.sound.play("bell_ring");
			} else if (data[i].indexOf('critical: ') != '-1') {
				toastr.error(data[i]);
				ion.sound.play("bell_ring");
			}
		}
	}
};

socket.onclose = function(event) {
  if (event.wasClean) {
    console.log(`[close] Соединение закрыто чисто, код=${event.code} причина=${event.reason}`);
  } else {
    console.log('[close] Соединение прервано');
  }
};

socket.onerror = function(error) {
  console.log(`[error] ${error.message}`);
};
function changePassword() {
	$("#user-change-password-table").dialog({
		autoOpen: true,
		resizable: false,
		height: "auto",
		width: 600,
		modal: true,
		title: "Change password",
		show: {
			effect: "fade",
			duration: 200
		},
		hide: {
			effect: "fade",
			duration: 200
		},
		buttons: {
			"Change": function () {
				changeUserPasswordItOwn($(this));
			},
			Cancel: function () {
				$(this).dialog("close");
				$('#missmatchpass').hide();
			}
		}
	});
}
function changeUserPasswordItOwn(d) {
	var pass = $('#change-password').val();
	var pass2 = $('#change2-password').val();
	if (pass != pass2) {
		$('#missmatchpass').show();
	} else {
		$('#missmatchpass').hide();
		toastr.clear();
		$.ajax({
			url: "/user/password",
			data: {
				updatepassowrd: pass,
				uuid: Cookies.get('uuid'),
				token: $('#token').val()
			},
			type: "POST",
			success: function (data) {
				data = data.replace(/\s+/g, ' ');
				if (data.indexOf('error:') != '-1') {
					toastr.error(data);
				} else {
					toastr.clear();
					d.dialog("close");
				}
			}
		});
	}
}
function waitForElm(selector) {
	return new Promise(resolve => {
		if (document.querySelector(selector)) {
			return resolve(document.querySelector(selector));
		}

		const observer = new MutationObserver(mutations => {
			if (document.querySelector(selector)) {
				resolve(document.querySelector(selector));
				observer.disconnect();
			}
		});

		observer.observe(document.body, {
			childList: true,
			subtree: true
		});
	});
}
function randomIntFromInterval(min, max) {
  return Math.floor(Math.random() * (max - min + 1) + min)
}
const removeEmptyLines = str => str.split(/\r?\n/).filter(line => line.trim() !== '').join('\n');
function show_version() {
	NProgress.configure({showSpinner: false});
	$.ajax( {
		url: "/internal/show_version",
		success: function( data ) {
			$('#version').html(data);
			var showUpdates = $( "#show-updates" ).dialog({
				autoOpen: false,
				width: 600,
				modal: true,
				title: 'There is a new RMON version',
				buttons: {
					Close: function() {
						$( this ).dialog( "close" );
						clearTips();
					}
				}
			});
			$('#show-updates-button').click(function() {
				showUpdates.dialog('open');
			});
		}
	} );
	NProgress.configure({showSpinner: true});
}
function show_pretty_ansible_error(data) {
	try {
		data = data.split('error: ');
		var p_err = JSON.parse(data[1]);
		return p_err['msg'];
	} catch (e) {
		return data;
	}
}
function openTab(tabId) {
	$( "#tabs" ).tabs( "option", "active", tabId );
}
function showPassword(input) {
  var x = document.getElementById(input);
  if (x.type === "password") {
    x.type = "text";
  } else {
    x.type = "password";
  }
}
function removeData() {
    let chart;
    for (let i = 0; i < charts.length; i++) {
        chart = charts[i];
        chart.destroy();
    }
}
function common_ajax_action_after_success(dialog_id, new_group, ajax_append_id, data) {
	toastr.clear();
	$("#"+ajax_append_id).append(data);
	$( "."+new_group ).addClass( "update", 1000);
	$.getScript(awesome);
	$.getScript('/static/js/users.js');
	clearTips();
	$( dialog_id ).dialog("close" );
	setTimeout(function() {
		$( "."+new_group ).removeClass( "update" );
	}, 2500 );
}
