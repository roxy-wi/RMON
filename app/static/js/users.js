var cur_url = window.location.href.split('/').pop();
cur_url = cur_url.split('/');
$( function() {
	$('#add-user-button').click(function() {
		addUserDialog.dialog('open');
	});
	let user_tabel_title = $( "#user-add-table-overview" ).attr('title');
	let addUserDialog = $( "#user-add-table" ).dialog({
		autoOpen: false,
		resizable: false,
		height: "auto",
		width: 600,
		modal: true,
		title: user_tabel_title,
		show: {
			effect: "fade",
			duration: 200
		},
		hide: {
			effect: "fade",
			duration: 200
		},
		buttons: [{
			text: add_word,
			click: function () {
				addUser(this);
			}
		}, {
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
				clearTips();
			}
		}]
	});
	$( "#ajax-users input" ).change(function() {
		var id = $(this).attr('id').split('-');
		updateUser(id[1])
	});
	$( "#ajax-users select" ).on('selectmenuchange',function() {
		var id = $(this).attr('id').split('-');
		updateUser(id[1])
	});
	$('#search_ldap_user').click(function() {
		var valid = true;
		toastr.clear();
		allFields = $([]).add($('#new-username'));
		allFields.removeClass("ui-state-error");
		valid = valid && checkLength($('#new-username'), "user name", 1);
		user = $('#new-username').val()
		if (valid) {
			$.ajax({
				url: "/user/ldap/" + $('#new-username').val(),
				success: function (data) {
					data = data.replace(/\s+/g, ' ');
					if (data.indexOf('error:') != '-1') {
						toastr.error(data);
						$('#new-email').val('');
						$('#new-password').attr('readonly', false);
						$('#new-password').val('');
					} else {
						var json = $.parseJSON(data);
						toastr.clear();
						if (!$('#new-username').val().includes('@')) {
							$('#new-username').val(user + '@' + json[1]);
						}
						$('#new-email').val(json[0]);
						$('#new-password').val('aduser');
						$('#new-password').attr('readonly', true);
					}
				}
			});
			clearTips();
		}
	});
	$("#tabs ul li").click(function() {
		var activeTab = $(this).find("a").attr("href");
		var activeTabClass = activeTab.replace('#', '');
		$('.menu li ul li').each(function () {
			$(this).find('a').css('border-left', '0px solid var(--right-menu-blue-color)');
			$(this).find('a').css('padding-left', '20px')
			$(this).find('a').css('background-color', 'var(--color-blue-light)');
			$(this).children("."+activeTabClass).css('padding-left', '30px');
			$(this).children("."+activeTabClass).css('border-left', '4px solid var(--right-menu-blue-color)');
			$(this).children("."+activeTabClass).css('background-color', 'var(--right-menu-blue-color)');
		});
		if (activeTab == '#tools') {
			loadServices();
		} else if (activeTab == '#updatehapwi') {
			loadupdatehapwi();
		}
	});
} );
window.onload = function() {
	$('#tabs').tabs();
	var activeTabIdx = $('#tabs').tabs('option','active')
	if (cur_url[0].split('#')[0] == 'admin') {
		if (activeTabIdx == 5) {
			loadServices();
		} else if (activeTabIdx == 6) {
			loadupdatehapwi();
		}
	}
}
function addUser(dialog_id) {
	toastr.clear();
	let valid = true;
	let new_username_div = $('#new-username');
	let password_div = $('#new-password');
	let email_div = $('#new-email');
	let allFields = $([]).add(new_username_div).add(password_div).add(email_div)
	allFields.removeClass("ui-state-error");
	valid = valid && checkLength(new_username_div, "user name", 1);
	valid = valid && checkLength(password_div, "password", 1);
	valid = valid && checkLength(email_div, "Email", 1);
	let enabled = 0;
	if ($('#enabled').is(':checked')) {
		enabled = '1';
	}
	let user_group = $('#new-group').val();
	if (user_group === undefined || user_group === null) {
		user_group = $('#new-sshgroup').val();
	}
	if (valid) {
		let jsonData = {
			"username": new_username_div.val(),
			"password": password_div.val(),
			"email": email_div.val(),
			"role": $('#new-role').val(),
			"enabled": enabled,
			"user_group": user_group,
		}
		$.ajax({
			url: "/user",
			type: "POST",
			data: JSON.stringify(jsonData),
			contentType: "application/json; charset=utf-8",
			success: function (data) {
				if (data.status === 'failed') {
					toastr.error(data.error);
				} else {
					let user_id = data.id;
					common_ajax_action_after_success(dialog_id, 'user-' + user_id, 'ajax-users', data.data);
				}
			}
		});
	}
}
function confirmDeleteUser(id) {
	 $( "#dialog-confirm" ).dialog({
      resizable: false,
      height: "auto",
      width: 400,
      modal: true,
	  title: delete_word + " " +$('#login-'+id).val() + "?",
      buttons: [{
		  text: delete_word,
		  click: function () {
			  $(this).dialog("close");
			  removeUser(id);
		  }
	  }, {
		  text: cancel_word,
		  click: function () {
			  $(this).dialog("close");
		  }
	  }]
    });
}
function removeUser(id) {
	$("#user-" + id).css("background-color", "#f2dede");
	$.ajax({
		url: api_v_prefix + "/user/" + id,
		contentType: "application/json; charset=utf-8",
		data: JSON.stringify({}),
		type: "DELETE",
		success: function (data) {
			if (data) {
				if (data.status === 'failed') {
					toastr.error(data.error);
				}
			} else {
				$("#user-" + id).remove();
			}
		}
	});
}
function updateUserRole(user_id, role_id) {
	let group_id = $('#new-sshgroup').val();
	$.ajax({
		url: api_v_prefix + "/user/" + user_id + "/groups/" + group_id,
		data: JSON.stringify({'role_id': role_id}),
		contentType: "application/json; charset=utf-8",
		type: "PUT",
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				toastr.remove();
				$("#user-" + id).addClass("update", 1000);
				setTimeout(function () {
					$("#user-" + id).removeClass("update");
				}, 2500);
			}
		}
	});
}
function updateUser(id) {
	let role = $('#role-' + id).val();
	let enabled = 0;
	if ($('#enabled-' + id).is(':checked')) {
		enabled = '1';
	}
	console.log(role)
	if (role == null && role !== undefined) {
		toastr.warning('You cannot edit superAdmin user');
		return false;
	}
	if (role !== null && role !== undefined) {
		updateUserRole(id, role);
	}
	toastr.remove();
	let json_data = {
		"username": $('#login-' + id).val(),
		"email": $('#email-' + id).val(),
		"enabled": enabled,
	}
	$.ajax({
		url: api_v_prefix + "/user/" + id,
		data: JSON.stringify(json_data),
		contentType: "application/json; charset=utf-8",
		type: "PUT",
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				toastr.remove();
				$("#user-" + id).addClass("update", 1000);
				setTimeout(function () {
					$("#user-" + id).removeClass("update");
				}, 2500);
			}
		}
	});
}
function showApacheLog(serv) {
	var rows = $('#rows').val();
	var grep = $('#grep').val();
	var exgrep = $('#exgrep').val();
	var hour = $('#time_range_out_hour').val();
	var minute = $('#time_range_out_minut').val();
	var hour1 = $('#time_range_out_hour1').val();
	var minute1 = $('#time_range_out_minut1').val();
	var url = "/logs/apache_internal/" + serv + "/" + rows;
	$.ajax( {
		url: url,
		data: {
			rows: rows,
			serv: serv,
			grep: grep,
			exgrep: exgrep,
			hour: hour,
			minute: minute,
			hour1: hour1,
			minute1: minute1
		},
		type: "POST",
		success: function( data ) {
			$("#ajax").html(data);
		}
	} );
}
function openChangeUserPasswordDialog(id) {
	changeUserPasswordDialog(id);
}
function changeUserPasswordDialog(id) {
	var cancel_word = $('#translate').attr('data-cancel');
	var superAdmin_pass = $('#translate').attr('data-superAdmin_pass');
	var change_word = $('#translate').attr('data-change2');
	var password_word = $('#translate').attr('data-password');
	if ($('#role-'+id + ' option:selected' ).val() == 'Select a role') {
		toastr.warning(superAdmin_pass);
		return false;
	}
	$( "#user-change-password-table" ).dialog({
		autoOpen: true,
		resizable: false,
		height: "auto",
		width: 600,
		modal: true,
		title: change_word + " " + $('#login-' + id).val() + " " + password_word,
		show: {
			effect: "fade",
			duration: 200
		},
		hide: {
			effect: "fade",
			duration: 200
		},
		buttons: [{
			text: change_word,
			click: function () {
				changeUserPassword(id, $(this));
			}
		}, {
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
				$('#missmatchpass').hide();
			}
		}]
	});
}
function changeUserPassword(id, d) {
	var pass = $('#change-password').val();
	var pass2 = $('#change2-password').val();
	if (pass != pass2) {
		$('#missmatchpass').show();
	} else {
		$('#missmatchpass').hide();
		toastr.clear();
		$.ajax({
			url: "/user/password/" + id,
			data: JSON.stringify({'pass': pass,}),
			type: "POST",
			contentType: "application/json; charset=utf-8",
			success: function (data) {
				if (data.status === 'failed') {
					toastr.error(data);
				} else {
					toastr.clear();
					$("#user-" + id).addClass("update", 1000);
					setTimeout(function () {
						$("#user-" + id).removeClass("update");
					}, 2500);
					d.dialog("close");
				}
			}
		});
	}
}
function confirmAjaxServiceAction(action, service) {
	let cancel_word = $('#translate').attr('data-cancel');
	let action_word = $('#translate').attr('data-'+action);
	$( "#dialog-confirm-services" ).dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: action_word + " " + service+"?",
		buttons: [{
			text: action_word,
			click: function () {
				$(this).dialog("close");
				ajaxActionServices(action, service);
			}
		}, {
			text: cancel_word,
			click: function() {
				$( this ).dialog( "close" );
			}
		}]
	});
}
function ajaxActionServices(action, service) {
	$.ajax( {
		url: "/admin/tools/action/" + service + "/" + action,
		success: function( data ) {
			if (data.indexOf('error:') != '-1' || data.indexOf('Failed') != '-1') {
				toastr.error(data);
			} else if (data.indexOf('warning: ') != '-1') {
				toastr.warning(data);
			} else {
				window.history.pushState("services", "services", cur_url[0].split("#")[0] + "#tools");
				toastr.success('The ' + service + ' has been ' + action +'ed');
				loadServices();
			}
		},
		error: function(){
			alert(w.data_error);
		}
	} );
}
function updateService(service, action='update') {
	$("#ajax-update").html('')
	$("#ajax-update").html(wait_mess);
	$.ajax({
		url: "/admin/tools/update/" + service,
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('Complete!') != '-1' || data.indexOf('Unpacking') != '-1') {
				toastr.clear();
				toastr.success(service + ' has been ' + action + 'ed');
			} else if (data.indexOf('Unauthorized') != '-1' || data.indexOf('Status code: 401') != '-1') {
				toastr.clear();
				toastr.error('It looks like there is no authorization in the RMON repository. Your subscription may have expired or there is no subscription. How to get the <b><a href="https://roxy-wi.org/pricing" title="Pricing" target="_blank">subscription</a></b>');
			} else if (data.indexOf('but not installed') != '-1') {
				toastr.clear();
				toastr.error('There is setting for RMON repository, but RMON is installed without repository. Please reinstall with package manager');
			} else if (data.indexOf('No Match for argument') != '-1' || data.indexOf('Unable to find a match') != '-1') {
				toastr.clear();
				toastr.error('It seems like RMON repository is not set. Please read docs for <b><a href="https://rmon.io/updates">detail</a></b>');
			} else if (data.indexOf('password for') != '-1') {
				toastr.clear();
				toastr.error('It seems like apache user needs to be added to sudoers. Please read docs for <b><a href="https://roxy-wi.org/installation#ansible">detail</a></b>');
			} else if (data.indexOf('No packages marked for update') != '-1') {
				toastr.clear();
				toastr.info('It seems like the latest version RMON is installed');
			} else if (data.indexOf('Connection timed out') != '-1') {
				toastr.clear();
				toastr.error('Cannot connect to RMON repository. Connection timed out');
			} else if (data.indexOf('--disable') != '-1') {
				toastr.clear();
				toastr.error('It seems like there is a problem with repositories');
			} else if (data.indexOf('Error: Package') != '-1') {
				toastr.clear();
				toastr.error(data);
			} else if (data.indexOf('conflicts with file from') != '-1') {
				toastr.clear();
				toastr.error(data);
			} else if (data.indexOf('error:') != '-1' || data.indexOf('Failed') != '-1') {
				toastr.error(data);
			} else if (data.indexOf('0 upgraded, 0 newly installed') != '-1') {
				toastr.info('There is no a new version of ' + service);
			} else {
				toastr.clear();
				toastr.success(service + ' has been ' + action + 'ed');
			}
			$("#ajax-update").html('');
			loadupdatehapwi();
			loadServices();
			show_version();
		}
	});
}
function loadServices() {
	$.ajax({
		url: "/admin/tools",
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('danger') != '-1' || data.indexOf('unique') != '-1' || data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				$('#ajax-services-body').html(data);
				$.getScript(awesome);
			}
		}
	} );
}
function loadupdatehapwi() {
	$.ajax({
		url: "/admin/update",
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('danger') != '-1' || data.indexOf('unique') != '-1' || data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				$('#ajax-updatehapwi-body').html(data);
			}
		}
	} );
}
function checkUpdateRoxy() {
	$.ajax({
		url: "/admin/update/check",
		success: function (data) {
			loadupdatehapwi();
		}
	} );
}
function confirmChangeGroupsAndRoles(user_id) {
	var cancel_word = $('#translate').attr('data-cancel');
	var action_word = $('#translate').attr('data-save');
	var user_groups_word = $('#translate').attr('data-user_groups');
	var username = $('#login-' + user_id).val();
	$.ajax({
		url: "/user/groups/" + user_id,
		success: function (data) {
			$("#groups-roles").html(data);
			$("#groups-roles").dialog({
				resizable: false,
				height: "auto",
				width: 700,
				modal: true,
				title: user_groups_word + ' ' + username,
				buttons: [{
					text: action_word,
					click: function () {
						saveGroupsAndRoles(user_id);
						$(this).dialog("close");
					}
				}, {
					text: cancel_word,
					click: function () {
						$(this).dialog("close");
					}
				}]
			});
		}
	});
}
function addGroupToUser(group_id) {
	var group_name = $('#add_group-'+group_id).attr('data-group_name');
	var group2_word = $('#translate').attr('data-group2');
	var length_tr = $('#all_groups tbody tr').length;
	const roles = {1: 'superAdmin', 2: 'admin', 3: 'user', 4: 'guest'};
	var options_roles = '';
	for (const [role_id, role_name] of Object.entries(roles)) {
		options_roles += '<option value="'+role_id+'">'+role_name+'</option>';
	}
	var tr_class = 'odd';
	if (length_tr % 2 != 0) {
		tr_class = 'even';
	}
	var html_tag = '<tr class="'+tr_class+'" id="remove_group-'+group_id+'" data-group_name="'+group_name+'">\n' +
		'        <td class="padding20" style="width: 50%;">'+group_name+'</td>\n' +
		'        <td style="width: 50%;">\n' +
		'            <select id="add_role-'+group_id+'">'+options_roles+'</select></td>\n' +
		'        <td><span class="remove_user_group" onclick="removeGroupFromUser('+group_id+')" title="'+delete_word+' '+group2_word+'">-</span></td></tr>'
	$('#add_group-'+group_id).remove();
	$("#checked_groups tbody").append(html_tag);
}
function removeGroupFromUser(group_id) {
	var group_name = $('#remove_group-'+group_id).attr('data-group_name');
	var add_word = $('#translate').attr('data-add');
	var group2_word = $('#translate').attr('data-group2');
	var length_tr = $('#all_groups tbody tr').length;
	var tr_class = 'odd';
	if (length_tr % 2 != 0) {
		tr_class = 'even';
	}
	var html_tag = '<tr class="'+tr_class+'" id="add_group-'+group_id+'" data-group_name='+group_name+'>\n' +
		'    <td class="padding20" style="width: 100%">'+group_name+'</td>\n' +
		'    <td><span class="add_user_group" title="'+add_word+' '+group2_word+'" onclick="addGroupToUser('+group_id+')">+</span></td></tr>'
	$('#remove_group-'+group_id).remove();
	$("#all_groups tbody").append(html_tag);
}
function saveGroupsAndRoles(user_id) {
	let jsonData = {};
	jsonData[user_id] = {};
	$('#checked_groups tbody tr').each(function () {
		let this_id = $(this).attr('id').split('-')[1];
		let role_id = $('#add_role-' + this_id).val();
		jsonData[user_id][this_id] = {'role_id': role_id};
	});
	for (const [key, value] of Object.entries(jsonData)) {
		if (Object.keys(value).length === 0) {
			toastr.error('error: User must have at least one group');
			return false;
		}
	}
	$.ajax({
		url: "/user/groups/save",
		data: {
			changeUserGroupsUser: $('#login-' + user_id).val(),
			jsonDatas: JSON.stringify(jsonData)
		},
		type: "POST",
		success: function (data) {
			if (data.indexOf('error: ') != '-1') {
				toastr.warning(data);
			} else {
				$("#user-" + user_id).addClass("update", 1000);
				setTimeout(function () {
					$("#user-" + user_id).removeClass("update");
				}, 2500);
			}
		}
	});
}
