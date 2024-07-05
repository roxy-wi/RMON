$( function() {
	$('#add-ssh-button').click(function () {
		addCredsDialog.dialog('open');
	});
	let ssh_tabel_title = $("#ssh-add-table-overview").attr('title');
	let addCredsDialog = $("#ssh-add-table").dialog({
		autoOpen: false,
		resizable: false,
		height: "auto",
		width: 600,
		modal: true,
		title: ssh_tabel_title,
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
				addCreds(this);
			}
		}, {
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
				clearTips();
			}
		}]
	});
	$("#ssh_enable_table input").change(function () {
		let id = $(this).attr('id').split('-');
		updateSSH(id[1])
		sshKeyEnableShow(id[1])
	});
	$("#ssh_enable_table select").on('selectmenuchange', function () {
		let id = $(this).attr('id').split('-');
		updateSSH(id[1])
		sshKeyEnableShow(id[1])
	});
	$('#new-ssh_enable').click(function () {
		if ($('#new-ssh_enable').is(':checked')) {
			$('#ssh_pass').css('display', 'none');
		} else {
			$('#ssh_pass').css('display', 'block');
		}
	});
	if ($('#new-ssh_enable').is(':checked')) {
		$('#ssh_pass').css('display', 'none');
	} else {
		$('#ssh_pass').css('display', 'block');
	}
});
function addCreds(dialog_id) {
	toastr.clear();
	let ssh_enable = 0;
	if ($('#new-ssh_enable').is(':checked')) {
		ssh_enable = '1';
	}
	let valid = true;
	let allFields = $([]).add($('#new-ssh-add')).add($('#ssh_user'))
	allFields.removeClass("ui-state-error");
	valid = valid && checkLength($('#new-ssh-add'), "Name", 1);
	valid = valid && checkLength($('#ssh_user'), "Credentials", 1);
	if (valid) {
        let jsonData = {
            "name": $('#new-ssh-add').val(),
            "group_id": $('#new-sshgroup').val(),
            "username": $('#ssh_user').val(),
            "password": $('#ssh_pass').val(),
            "key_enabled": ssh_enable
        }
		$.ajax({
			url: api_v_prefix + "/server/cred",
			data: JSON.stringify(jsonData),
			contentType: "application/json; charset=utf-8",
			type: "POST",
			success: function (data) {
				if (data.status === 'failed') {
					toastr.error(data.error);
				} else {
					let group_name = getGroupNameById($('#new-sshgroup').val());
					let id = data.id;
					common_ajax_action_after_success(dialog_id, 'ssh-table-' + id, 'ssh_enable_table', data.data);
					$('select:regex(id, credentials)').append('<option value=' + id + '>' + $('#new-ssh-add').val() + '</option>').selectmenu("refresh");
					$('select:regex(id, ssh-key-name)').append('<option value=' + id + '_' + group_name + '>' + $('#new-ssh-add').val() + '_' + group_name + '</option>').selectmenu("refresh");
					$("input[type=submit], button").button();
					$("input[type=checkbox]").checkboxradio();
					$("select").selectmenu();
				}
			}
		});
	}
}
function sshKeyEnableShow(id) {
	$('#ssh_enable-'+id).click(function() {
		if ($('#ssh_enable-'+id).is(':checked')) {
			$('#ssh_pass-'+id).css('display', 'none');
		} else {
			$('#ssh_pass-'+id).css('display', 'block');
		}
	});
	if ($('#ssh_enable-'+id).is(':checked')) {
		$('#ssh_pass-'+id).css('display', 'none');
	} else {
		$('#ssh_pass-'+id).css('display', 'block');
	}
}
function confirmDeleteSsh(id) {
	$( "#dialog-confirm" ).dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: delete_word +" " + $('#ssh_name-' + id).val() + "?",
		buttons: [{
			text: delete_word,
			click: function () {
				$(this).dialog("close");
				removeSsh(id);
			}
		},{
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
			}
		}]
	});
}
function removeSsh(id) {
	$("#ssh-table-" + id).css("background-color", "#f2dede");
	$.ajax({
		url: api_v_prefix + "/server/cred/" + id,
		contentType: "application/json; charset=utf-8",
		type: "DELETE",
		statusCode: {
			204: function (xhr) {
				$("#ssh-table-" + id).remove();
				$('select:regex(id, credentials) option[value=' + id + ']').remove();
				$('select:regex(id, credentials)').selectmenu("refresh");
			},
			404: function (xhr) {
				$("#ssh-table-" + id).remove();
				$('select:regex(id, credentials) option[value=' + id + ']').remove();
				$('select:regex(id, credentials)').selectmenu("refresh");
			}
		},
		success: function (data) {
			if (data) {
				if (data.status === 'failed') {
					toastr.error(data.error);
				}
			}
		}
	});
}
function uploadSsh() {
    toastr.clear();
    if ($("#ssh-key-name option:selected").val() == "------" || $('#ssh_cert').val() == '') {
        toastr.error('All fields must be completed');
        return false;
    }
	let jsonData = {
		"private_key": $('#ssh_cert').val(),
		"passphrase": $('#ssh-key-pass').val(),
	}
    $.ajax({
        url: api_v_prefix + "/server/cred/" + $('#ssh-key-name').val(),
        data: JSON.stringify(jsonData),
		contentType: "application/json; charset=utf-8",
        type: "PATCH",
        success: function (data) {
            if (data.status === 'failed') {
                toastr.error(data.error);
            } else {
                toastr.clear();
                toastr.success('The SSH key has been loaded')
            }
        }
    });
}
function updateSSH(id) {
	toastr.clear();
	let ssh_enable = 0;
	if ($('#ssh_enable-' + id).is(':checked')) {
		ssh_enable = '1';
	}
	let group = $('#sshgroup-' + id).val();
	let jsonData = {
		"name": $('#ssh_name-' + id).val(),
		"group": group,
		"key_enabled": ssh_enable,
		"username": $('#ssh_user-' + id).val(),
		"password": $('#ssh_pass-' + id).val(),
		"id": id,
	}
	$.ajax({
		url: "/server/cred",
		data: JSON.stringify(jsonData),
		contentType: "application/json; charset=utf-8",
		type: "PUT",
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				toastr.clear();
				$("#ssh-table-" + id).addClass("update", 1000);
				setTimeout(function () {
					$("#ssh-table-" + id).removeClass("update");
				}, 2500);
				$('select:regex(id, credentials) option[value=' + id + ']').remove();
				$('select:regex(id, ssh-key-name) option[value=' + $('#ssh_name-' + id).val() + ']').remove();
				$('select:regex(id, credentials)').append('<option value=' + id + '>' + $('#ssh_name-' + id).val() + '</option>').selectmenu("refresh");
				$('select:regex(id, ssh-key-name)').append('<option value=' + $('#ssh_name-' + id).val() + '>' + $('#ssh_name-' + id).val() + '</option>').selectmenu("refresh");
			}
		}
	});
}
