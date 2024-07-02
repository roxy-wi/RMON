$( function() {
	$( "#ajax-group input" ).change(function() {
		var id = $(this).attr('id').split('-');
		updateGroup(id[1])
	});
    $('#add-group-button').click(function () {
        addGroupDialog.dialog('open');
    });
    let group_tabel_title = $("#group-add-table-overview").attr('title');
    let addGroupDialog = $("#group-add-table").dialog({
        autoOpen: false,
        resizable: false,
        height: "auto",
        width: 600,
        modal: true,
        title: group_tabel_title,
        show: {
            effect: "fade",
            duration: 200
        },
        hide: {
            effect: "fade",
            duration: 200
        },
        buttons: {
            "Add": function () {
                addGroup(this);
            },
            Cancel: function () {
                $(this).dialog("close");
                clearTips();
            }
        }
    });
});
function addGroup(dialog_id) {
    toastr.clear();
    let valid = true;
    let allFields = $([]).add($('#new-group-add'));
    allFields.removeClass("ui-state-error");
    valid = valid && checkLength($('#new-group-add'), "new group name", 1);
    if (valid) {
        let json_data = {
            "name": $('#new-group-add').val(),
            "desc": $('#new-desc').val()
        }
        $.ajax({
            url: "/group",
            data: JSON.stringify(json_data),
            contentType: "application/json; charset=utf-8",
            type: "POST",
            success: function (data) {
                if (data.status === 'failed') {
                    toastr.error(data.error);
                } else {
                    let id = data.id;
                    $('select:regex(id, group)').append('<option value=' + id + '>' + $('#new-group-add').val() + '</option>').selectmenu("refresh");
                    common_ajax_action_after_success(dialog_id, 'newgroup', 'ajax-group', data.data);
                }
            }
        });
    }
}
function getGroupNameById(group_id) {
	let group_name = ''
	$.ajax({
		url: "/user/group/name/" + group_id,
		async: false,
		success: function (data) {
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				group_name = data;
			}
		}
	});
	return group_name;
}
function confirmDeleteGroup(id) {
    $("#dialog-confirm").dialog({
        resizable: false,
        height: "auto",
        width: 400,
        modal: true,
        title: delete_word + " " + $('#name-' + id).val() + "?",
        buttons: [{
            text: delete_word,
            click: function () {
                $(this).dialog("close");
                removeGroup(id);
            }
        }, {
            text: cancel_word,
            click: function () {
                $(this).dialog("close");
            }
        }]
    });
}
function removeGroup(id) {
    $("#group-" + id).css("background-color", "#f2dede");
    $.ajax({
        url: api_v_prefix + "/group/" + id,
        type: "DELETE",
        contentType: "application/json; charset=utf-8",
		statusCode: {
			204: function (xhr) {
				$("#group-" + id).remove();
                $('select:regex(id, group) option[value=' + id + ']').remove();
                $('select:regex(id, group)').selectmenu("refresh");
			},
			404: function (xhr) {
				$("#group-" + id).remove();
                $('select:regex(id, group) option[value=' + id + ']').remove();
                $('select:regex(id, group)').selectmenu("refresh");
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
function updateGroup(id) {
    toastr.clear();
    let json_data = {
        "name": $('#name-' + id).val(),
        "desc": $('#descript-' + id).val()
    }
    $.ajax({
        url: api_v_prefix + "/group/" + id,
        data: JSON.stringify(json_data),
        contentType: "application/json; charset=utf-8",
        type: "PUT",
        success: function (data) {
            if (data.status === 'failed') {
                toastr.error(data.error);
            } else {
                toastr.clear();
                $("#group-" + id).addClass("update", 1000);
                setTimeout(function () {
                    $("#group-" + id).removeClass("update");
                }, 2500);
                $('select:regex(id, group) option[value=' + id + ']').remove();
                $('select:regex(id, group)').append('<option value=' + id + '>' + $('#name-' + id).val() + '</option>').selectmenu("refresh");
            }
        }
    });
}
