odoo.define('odoo_inbox.odoo_inbox', function(require) {
    'use strict';
    require('web.dom_ready');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var time = require('web.time');
    var publicWidget = require('web.public.widget');
    var session = require('web.session');
    var Widget = require('web.Widget');
    var qweb = core.qweb;
    var _t = core._t;
    $.blockUI.defaults.css.border = '0';
    $.blockUI.defaults.css["background-color"] = '';
    $.blockUI.defaults.overlayCSS["opacity"] = '0.9';

    function isInteger(str) {
        const num = parseInt(str, 10);
        return !isNaN(num) && num.toString() === str;
    }

    publicWidget.registry.OdooInbox = publicWidget.Widget.extend({
        // xmlDependencies: ['/odoo_inbox/static/src/xml/website.xml'],
        selector: '.odoo_inbox_page',
        events: {
            'click .message__summary .message__summary__icon': '_onMessageSummaryClick',
            'click .message__summary .message__summary__title': '_onMessageSummaryClick',
            'click .message__summary .message__summary__body': '_onMessageSummaryClick',
            'click .message__details__header': '_onMessageDetailsHeader',
            'click .right a.button-exit': '_onRightButtonExit',
            'click .message__details__footer .detail_mail_addrss span': '_onDetailMessageReply',
            'click .reply_delete_bttn': '_onReplyDeleteButtonClick',
            'click .starred_btn i': '_onStarredButtonIconClick',
            'click .mark_as_done i': '_onMarkAsDoneButtonIconClick',
            'click .arrow': '_onArrowClick',
            'click .tag_edit_save_btn': '_onClickButtonClosestFormSubmit',
            'click .tag_delete_save_btn': '_onClickButtonClosestFormSubmit',
            'click .folder_edit_save_btn': '_onClickButtonClosestFormSubmit',
            'click .folder_delete_save_btn': '_onClickButtonClosestFormSubmit',
            'click .remove_tag': '_onRemoveTagClick',
            'click .tag-dropdown-menu, .label-container': '_onTagDropDownLabelClick',
            'click .body_content .tag-dropdown-menu .apply_button a': '_onTagDropDownApplyButtonClick',
            'click .all_mssg_to_tag .tag-dropdown-menu .apply_button a': '_onAllMessageTagApplyButtonClick',
            'click .create_folder_input, .folder-dropdown-menu .apply_button': '_onFolderDropDownApplyButton',
            'click .button-fullscreen': '_onButtonFullScreenClick',
            'click .button-minimize': '_onButtonMinimizeClick',
            'click .open_newmail': '_onOpenNewMailClick',
            'click .mail-option .selectall': '_onMailOptionSelectAll',
            'click .individual': '_onIndividualCheckBoxClick',
            'click .movetofolder': '_onMoveFolderClick',
            'click .all_mssg_starred': '_onAllMessageStarredClick',
            'click .all_mssg_unstarred': '_onAllMessageUnStarredClick',
            'click .all_mssg_unread': '_onAllMessageUnReadClick',
            'click .all_mssg_read': '_onAllMessageReadClick',
            'click .gmail_snooze_child_menu a': '_onSnoozeChildMenuAClick',
            'click .snooze_date_submit': '_onSnoozeDateSubmitClick',
            'click .all_mssg_to_trash': '_onAllMessageToTrash',
            'click .all_mssg_to_done': '_onAllMessageToDone',
            'click .burger_container': '_onBurgerShowCategoriesClick',
            'mouseover #oe_applications:not(:has(.dropdown-item))': '_onOeApplicationsHovered',
            'change #document_model': '_onChangeDocumentModel',
            'change #document_model_records': '_onChangeDocumentRecord',
            'change #document_compose_mail_template': '_onChangeDocumentMailTemplate',
            'click #btn_compose_save_template': '_onClickComposeSaveTemplate',
            'click .dropdown_pane_type_view_select .dropdown-item': '_onClickPaneTypeSelect',
            'click .single_message_back': '_onClickSingleMessageBack',
            'click .inbox_theme_list .inbox_theme_image': '_onClickInboxThemeImage',
            'click .inbox_theme_list .inbox_theme_color': '_onClickInboxThemeColor',
            'click .message__details__footer .print_email': '_onClickPrintEmail',
        },
        init: function() {
            this._super.apply(this, arguments);
        },
        start: function() {
            var self = this;
            var res = this._super.apply(this, arguments)
            var datepickers_options = {
                calendarWeeks: true,
                icons: {
                    time: 'fa fa-clock-o',
                    date: 'fa fa-calendar',
                    up: 'fa fa-chevron-up',
                    down: 'fa fa-chevron-down'
                },
            }
            $('div[id^=datetimepicker]').datetimepicker(datepickers_options);
            $('div[id^=snoozedatePicker]').datetimepicker(datepickers_options);

            self._loadEditor();
            self._loadPartnerSelect();
            if (($(window).width() >= 767)) {
                $('#menu').css({
                    'display': 'block'
                })
            }
            if (($(window).width() < 768)) {
                $('#menu').addClass('small-width');
                $('#menu .plist').toggle();
                $('.wrapper').addClass('full-wrapper');
            }
            $('[data-toggle="tooltip"]').tooltip();
            $('#dropdown_separate_snoze').parent().on('hide.bs.dropdown', function(e) {
                e.preventDefault();
            });
            self._onOeApplicationsHovered();
            if ($(".inbox_mail_list").hasClass('resizable')) {
                $(".inbox_mail_list").nresizable('destroy');
                $('.inbox_mail_list').removeAttr("style");
            }
            $('.vertical-resize').find(".inbox_mail_list").nresizable({
                handleSelector: ".inbox_mail_spliter",
                resizeHeight: false,
                minWidth: '20%',
                maxWidth: '80%',
            });
            $('.horizontal-resize').find(".inbox_mail_list").nresizable({
                handleSelector: ".inbox_mail_spliter",
                hresizeWidth: false,
                minHeight: '20%',
                maxHeight: '80%',
            });

            const currentUrl = window.location.href;
            const url = new URL(currentUrl);
            const params = new URLSearchParams(url.search);
            const to_email = params.get('to_email');
            if (to_email) {
                this._onOpenNewMailClick();
                $.ajax({
                    url: "/mail/get_res_partners",
                    type: "POST",
                    contentType: "application/json",
                    data: JSON.stringify({
                        q: to_email, // Replace with your search term
                        page: 1, // Replace with the desired page number
                        jsonrpc: "2.0",
                        params: {
                            kwargs: {
                                q: to_email, // Same search term
                                page: 1, // Same page number
                            },
                            q: to_email, // Same search term
                            page: 1, // Same page number
                        }
                    }),
                    success: function(data) {
                        if (data.result.items.length)
                            $("#compose_partner").select2("trigger", "select", {
                                data: data.result.items[0]
                            });
                    },
                    error: function(xhr, status, error) {
                        // Handle any errors
                        console.error("Error occurred:", status, error);
                    }
                });
            }
            return res;
        },
        _onClickPrintEmail: function() {
            const printWindow = window.open('', '', '');
            printWindow.document.write($('.message__details__body__content').html());
            printWindow.document.close(); // Close the document to apply styles
            printWindow.focus(); // Focus on the new window
            printWindow.print(); // Trigger the print dialog
            printWindow.onafterprint = function() {
                printWindow.close();
            };
        },
        removeLoading: function(xmlid, render_values) {
            $.unblockUI();
        },
        displayLoading: function(mail) {
            if (mail){
                var msg = _t("The Mail template is being rendered, please wait ...");
            } else {
                var msg = _t("We are processing, please wait ...");
            }
            $.blockUI({
                'message': '<h2 class="text-white"><img src="/web/static/img/spin.png" class="fa-pulse"/>' +
                    '    <br />' + msg +
                    '</h2>'
            });
        },
        /**
         * Called when the backend applications menu is hovered -> fetch the
         * available menus and insert it in DOM.
         *
         * @private
         * @param {Event} ev
        */
        _onOeApplicationsHovered: function (ev) {
            var self = this;
            var menuInfo = [];
            console.log("SSession_info:", odoo.session_info);
            console.log("User context:", odoo.session_info.user_context);
            console.log("User lang:", odoo.session_info.user_context.lang);

            this._rpc({
                model: 'ir.ui.menu',
                method: 'load_menus_root',
                args: [],
                kwargs: {
                    context: {
                        lang: odoo.session_info.user_context.lang,
                    },
                },
            }).then(function (result) {

                console.log("RPC result:", result);
                console.log("Returned menu names:");

                result.children.forEach((e, i) => {
                    console.log("Menu:", e.name);

                    if (e.web_icon_data) {
                        var decode_icon = atob(e.web_icon_data);
                        try {
                            var iconFormat = decode_icon.split(';')[0].split('/')[4].split(" ")[0].split('"')[0];
                        } catch (e) {
                            var iconFormat = 'png';
                        }

                        menuInfo.push({
                            id: e.id,
                            action: e.action,
                            parent_id: e.parent_id,
                            iconFormat: iconFormat,
                            name: e.name,
                            web_icon_data: e.web_icon_data,
                            icon: decode_icon,
                        });
                    }
                });

                self.$('#oe_applications .dropdown-menu').html(
                    $(qweb.render('inbox.oe_applications_menu', { menu_data: menuInfo }))
                );
            });
        },

        _onClickPaneTypeSelect: function(ev) {
            var split_data = $(ev.currentTarget).data('split-type');
            $('.inbox_mail_container').removeClass('horizontal-resize');
            $('.inbox_mail_container').removeClass('none-resize');
            $('.inbox_mail_container').removeClass('vertical-resize');
            if ($(".inbox_mail_list").hasClass('resizable')) {
                $(".inbox_mail_list").nresizable('destroy');
                $('.inbox_mail_list').removeAttr("style");
            }
            if (split_data == 'vertical') {
                $('.inbox_mail_container').addClass('vertical-resize');
                $('.vertical-resize').find(".inbox_mail_list").nresizable({
                    handleSelector: ".inbox_mail_spliter",
                    resizeHeight: false,
                    minWidth: '20%',
                    maxWidth: '80%',
                });
            } else if (split_data == 'horizontal') {
                $('.inbox_mail_container').addClass('horizontal-resize');
                $('.horizontal-resize').find(".inbox_mail_list").nresizable({
                    handleSelector: ".inbox_mail_spliter",
                    hresizeWidth: false,
                    minHeight: '20%',
                    maxHeight: '80%',
                });
            } else {
                $('.inbox_mail_container').addClass('none-resize');
            }
            var value = {};
            value['inbox_default_pane_view_type'] = split_data
            rpc.query({
                model: 'res.users',
                method: 'set_inbox_setting_user',
                args: [session.user_id],
                kwargs: value,
            }).then(function(res) {});
        },
        _onBurgerShowCategoriesClick: function() {
            // Burger Menu Click
            $('#menu .plist').toggle();
            if ($('#menu .plist').is(':visible')) {
                $('#menu').removeClass('small-width');
                $('.wrapper').removeClass('full-wrapper');
            } else {
                $('#menu').addClass('small-width');
                $('.wrapper').addClass('full-wrapper');
            }
        },
        _onClickSingleMessageBack: function() {
            $('.inbox_mail_list').removeClass('deactive');
            $('.inbox_mail_main_body').removeClass('active');
            $('.mail-multiple-message-options').removeClass('d-none');
            $('.mail-single-message-options').addClass('d-none');
        },
        validateEmail: function(email) {
            var re = /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
            return re.test(email);
        },
        _loadEditor: function() {
            //Load Summer Not Editor
            $('textarea.load_editor').each(function() {
                var $textarea = $(this);
                if (!$textarea.val().match(/\S/)) {
                    $textarea.val("<p><br/></p>");
                }
                var $form = $textarea.closest('form');
                var toolbar = [
                    ['style', ['style']],
                    ['font', ['bold', 'italic', 'underline', 'clear']],
                    ['para', ['ul', 'ol', 'paragraph']],
                    ['table', ['table']],
                    ['history', ['undo', 'redo']],
                ];
                $textarea.summernote({
                    height: 320,
                    toolbar: toolbar,
                    styleWithSpan: false,
                    placeholder: 'Say something'
                });

                $form.on('click', 'button, .a-submit', function() {
                    $textarea.html($form.find('.note-editable').html());
                });
            });


            $.ajax({
                url: 'https://api.github.com/emojis',
                async: false
            }).then(function(data) {
                window.emojis = Object.keys(data);
                window.emojiUrls = data;
            });

            // document.emojiType = 'unicode'; // default: image

            document.emojiSource = '/odoo_inbox/static/src/img/';

            $('textarea.load_editor1').each(function() {
                var $textarea = $(this);
                if (!$textarea.val().match(/\S/)) {
                    $textarea.val("<p><br/></p>");
                }
                var $form = $textarea.closest('form');
                var toolbar = [
                    ['style', ['style']],
                    ['font', ['bold', 'italic', 'underline', 'clear']],
                    ['para', ['ul', 'ol', 'paragraph']],
                    ['table', ['table']],
                    ['history', ['undo', 'redo']],
                    // ['insert', ['emoji']],
                    ['code', ['codeview']],
                ];
                $textarea.summernote({
                    height: 120,
                    toolbar: toolbar,
                    styleWithSpan: false,
                    focus: true,
                    hint: {
                        match: /:([\-+\w]+)$/,
                        search: function(keyword, callback) {
                            callback($.grep(emojis, function(item) {
                                return item.indexOf(keyword) === 0;
                            }));
                        },
                        template: function(item) {
                            var content = emojiUrls[item];
                            return '<img src="' + content + '" width="20" /> :' + item + ':';
                        },
                        content: function(item) {
                            var url = emojiUrls[item];
                            if (url) {
                                return $('<img />').attr('src', url).css('width', 20)[0];
                            }
                            return '';
                        }
                    },
                    callbacks: {
                        onKeyup: function(event) {
                            setTimeout(function() {
                                var content = $(".load_editor1").val().replace(/<\/?[^>]+(>|$)/g, "");
                                var entered = content.split(' ').pop();
                                if (entered.length > 1 && entered.substring(0, 1) == '@') {
                                    var search = entered.substring(1, entered.length);
                                    rpc.query({
                                        model: 'res.partner',
                                        method: 'get_mention_suggestions',
                                        args: [search, 5]
                                    }).then(function(res) {
                                        var scontent = '';
                                        $.each(res[0], function(index, suggestion) {
                                            var tml = '<li class="o_mention_proposition" data-id="' + suggestion.id + '"><span class="o_mention_name">' + suggestion.name + '</span><span class="o_mention_info">(' + suggestion.email + ')</span></li>';
                                            scontent += tml;
                                        });
                                        $('div.o_composer_mention_dropdown ul').html(scontent);
                                        $('div.o_composer_mention_dropdown').addClass('open');
                                        $('div.o_composer_mention_dropdown').attr('data-content', entered);

                                        $('div.o_composer_mention_dropdown li').click(function() {
                                            var user_id = $(this).attr('data-id');
                                            var username = $(this).find('.o_mention_name').text();
                                            var data_content = $('div.o_composer_mention_dropdown').attr('data-content');
                                            var upt_content = $(".load_editor1").val().replace(data_content, username);
                                            $('.load_editor1').summernote('code', upt_content);

                                            var $input_user_ids = $(this).parents('.reply_body_content').find('input[name=users_ids]');
                                            if ($input_user_ids.val()) {
                                                var updated_values = $input_user_ids.val() + ',' + user_id;
                                                $input_user_ids.val(updated_values);
                                            } else {
                                                $input_user_ids.val(user_id);
                                            }
                                            $('div.o_composer_mention_dropdown').removeClass('open');
                                        });
                                    });
                                } else {
                                    $('div.o_composer_mention_dropdown').removeClass('open');
                                }
                            }, 200);
                        }
                    }
                });

                $form.on('click', 'button, .a-submit', function() {
                    // $textarea.html($form.find('.note-editable').code());
                });
            });
        },
        _loadPartnerSelect: function() {
            // Load Partber Select2 and create new parter if email is valid from select
            var self = this;
            $('#compose_partner').select2({
                ajax: {
                    url: "/mail/get_res_partners",
                    delay: 250,
                    type: "POST",
                    contentType: "application/json",
                    data: function(params) {
                        return JSON.stringify({
                            q: params.term, // search term
                            page: params.page,
                            jsonrpc: "2.0",
                            params: {
                                kwargs: {
                                    q: params.term,
                                    page: params.page,
                                },
                                q: params.term,
                                page: params.page,
                            }
                        });
                    },
                    processResults: function(data, params) {
                        // console.log(data);
                        // data = JSON.parse(data);
                        params.page = params.page || 1;
                        return {
                            results: data.result.items,
                            pagination: {
                                more: (params.page * 30) < data.total_count
                            }
                        };
                    },
                    cache: true,
                },
                width: '100%',
                placeholder: "To",
                allowClear: true,
                minimumInputLength: 2,
                tags: true,
                createTag: function(params) {
                    var value = params.term;
                    if (self.validateEmail(value)) {
                        return {
                            id: value,
                            text: value,
                            newTag: true,
                        };
                    }
                    return null;
                },
            }).on('select2:select', function(evt) {
                if (evt.params.data.newTag) {
                    ajax.jsonRpc('/mail/partner_create', 'call', {
                        email_address: evt.params.data.text,
                    }).then(function(data) {
                        $('#compose_partner option[value="' + evt.params.data.text + '"]').text(data.partner_name);
                        $('#compose_partner option[value="' + evt.params.data.text + '"]').text(data.email);
                        $('#compose_partner option[value="' + evt.params.data.text + '"]').attr('value', data.partner_id);
                    });
                }
            });

            $('#compose_tags').select2({
                ajax: {
                    url: "/web/dataset/call_kw/res.partner.category/name_search",
                    delay: 250,
                    type: "POST",
                    contentType: "application/json",
                    data: function(params) {
                        return JSON.stringify({
                          "id": 26,
                          "jsonrpc": "2.0",
                          "method": "call",
                          "params": {
                            "model": "res.partner.category",
                            "method": "name_search",
                            "args": [],
                            "kwargs": {
                              "name": params.term,
                              "operator": "ilike",
                              "args": [
                                "!",
                                [
                                  "id",
                                  "in",
                                  []
                                ]
                              ],
                              "limit": 8,
                              "context": {
                                "lang": "de_DE",
                                "tz": "Europe/Zurich",
                                "uid": 10,
                                "allowed_company_ids": [
                                  1
                                ]
                              }
                            }
                          }
                        });
                    },
                    processResults: function(data, params) {
                        params.page = params.page || 1;
                        return {
                            results: data.result.map(item => ({id: item[0], text: item[1]})),
                            pagination: {
                                more: (params.page * 30) < data.total_count
                            }
                        };
                    },
                    cache: true,
                },
                width: '100%',
                placeholder: "Tags",
                allowClear: true,
                minimumInputLength: 2,
                tags: true,
                createTag: function(params) {
                    var value = params.term;
                    return null;
                },
            }).on('select2:select', function(evt) {
                const id = evt.params.data.id;
                ajax.jsonRpc('/mail/get_partner_from_category', 'call', {
                    category_id: id
                }).then(function(data) {
                // Check if the div exists after .to-tags, if not, create it and set the content
                    var $toTagsDiv = $('.to-tags');
                    if ($toTagsDiv.length) {
                        var $nextDiv = $toTagsDiv.next('.partner-category-result');
                        if (!$nextDiv.length) {
                            $nextDiv = $('<div class="partner-category-result"></div>');
                            $toTagsDiv.after($nextDiv);
                        }
                        // Set the content, for example, list partner names if data.success
                        if (data.length) {
                            var html = $nextDiv.html();
                            data.forEach(function(partner) {
                                // partner could be a recordset, so try to get name/email/id
                                var name = partner.name || partner.display_name || partner.email || partner.id || '';
                                html += `${_.escape(name)}&lt;${partner.email}&gt; , `;
                            });
                            $nextDiv.html(html);
                        } else if (data && data.error) {
                            $nextDiv.html('<span class="text-danger">' + _.escape(data.error) + '</span>');
                        } else {
                            $nextDiv.html('');
                        }
                    }
                })
                if (evt.params.data.newTag) {
                    ajax.jsonRpc('/mail/partner_create', 'call', {
                        email_address: evt.params.data.text,
                    }).then(function(data) {
                        $('#compose_tags option[value="' + evt.params.data.text + '"]').text(data.partner_name);
                        $('#compose_tags option[value="' + evt.params.data.text + '"]').text(data.email);
                        $('#compose_tags option[value="' + evt.params.data.text + '"]').attr('value', data.partner_id);
                    });
                }
            });

            $('#cc_compose_partner').select2({
                ajax: {
                    url: "/mail/get_res_partners",
                    delay: 250,
                    type: "POST",
                    contentType: "application/json",
                    data: function(params) {
                        return JSON.stringify({
                            q: params.term, // search term
                            page: params.page,
                            jsonrpc: "2.0",
                            params: {
                                kwargs: {
                                    q: params.term,
                                    page: params.page,
                                },
                                q: params.term,
                                page: params.page,
                            }
                        });
                    },
                    processResults: function(data, params) {
                        // console.log(data);
                        // data = JSON.parse(data);
                        params.page = params.page || 1;
                        return {
                            results: data.result.items,
                            pagination: {
                                more: (params.page * 30) < data.total_count
                            }
                        };
                    },
                    cache: true,
                },
                width: '100%',
                placeholder: "Cc",
                allowClear: true,
                tags: true,
                createTag: function(params) {
                    var value = params.term;
                    if (self.validateEmail(value)) {
                        return {
                            id: value,
                            text: value,
                            newTag: true,
                        };
                    }
                    return null;
                },
            }).on('select2:select', function(evt) {
                if (evt.params.data.newTag) {
                    ajax.jsonRpc('/mail/partner_create', 'call', {
                        email_address: evt.params.data.text,
                    }).then(function(data) {
                        $('#cc_compose_partner option[value="' + evt.params.data.text + '"]').text(data.partner_name);
                        $('#cc_compose_partner option[value="' + evt.params.data.text + '"]').text(data.email);
                        $('#cc_compose_partner option[value="' + evt.params.data.text + '"]').attr('value', data.partner_id);
                    });
                }
            });

            $('#bcc_compose_partner').select2({
                ajax: {
                    url: "/mail/get_res_partners",
                    delay: 250,
                    type: "POST",
                    contentType: "application/json",
                    data: function(params) {
                        return JSON.stringify({
                            q: params.term, // search term
                            page: params.page,
                            jsonrpc: "2.0",
                            params: {
                                kwargs: {
                                    q: params.term,
                                    page: params.page,
                                },
                                q: params.term,
                                page: params.page,
                            }
                        });
                    },
                    processResults: function(data, params) {
                        // console.log(data);
                        // data = JSON.parse(data);
                        params.page = params.page || 1;
                        return {
                            results: data.result.items,
                            pagination: {
                                more: (params.page * 30) < data.total_count
                            }
                        };
                    },
                    cache: true,
                },
                width: '100%',
                placeholder: "Bcc",
                allowClear: true,
                tags: true,
                createTag: function(params) {
                    var value = params.term;
                    if (self.validateEmail(value)) {
                        return {
                            id: value,
                            text: value,
                            newTag: true,
                        };
                    }
                    return null;
                },
            }).on('select2:select', function(evt) {
                if (evt.params.data.newTag) {
                    ajax.jsonRpc('/mail/partner_create', 'call', {
                        email_address: evt.params.data.text,
                    }).then(function(data) {
                        $('#bcc_compose_partner option[value="' + evt.params.data.text + '"]').text(data.partner_name);
                        $('#bcc_compose_partner option[value="' + evt.params.data.text + '"]').text(data.email);
                        $('#bcc_compose_partner option[value="' + evt.params.data.text + '"]').attr('value', data.partner_id);
                    });
                }
            });

            
            $('#document_model').select2({
                width: '100%',
                placeholder: "Select Document",
            });
            $('#document_model_records').select2({
                width: '100%',
                placeholder: "Select Record",
            });
            self._getMailTemplates('inbox.mail.template');
            $('#document_compose_mail_template').select2({
                width: '100%',
                placeholder: "Select Template",
            });
        },
        _onMessageSummaryClick: function(event) {
            var self = this;
            self.displayLoading();
            var $remove = $(event.currentTarget).closest('.message__summary');
            var message = $remove.data('message');
            // $('#wrapper .message').removeClass("message--open").css('margin-top', '0%').css('margin-bottom', '0%');
            // $(event.currentTarget).closest('.message').addClass("message--open");
            // $(event.currentTarget).closest('.message').css('margin-top', '3%').css('margin-bottom', '3%');
            $('.inbox_mail_list').removeClass('deactive');
            $('.inbox_mail_main_body').removeClass('active');
            $('.mail-multiple-message-options').removeClass('d-none');
            $('.mail-single-message-options').addClass('d-none');
            if ($('.inbox_mail_container').hasClass('none-resize')) {
                $('.inbox_mail_list').addClass('deactive');
                $('.inbox_mail_main_body').addClass('active');
                $('.mail-multiple-message-options').addClass('d-none');
                $('.mail-single-message-options').removeClass('d-none');
            }
            var vals = location.pathname.split('/');
            ajax.jsonRpc('/mail/'+(isInteger(vals[2])?vals[2]:vals[3])+'/message_read', 'call', {
                message: message,
            }).then(function(data) {
                // data['msg_unread']
                $remove.removeClass('gmail_unread');
                $remove.addClass('gmail_read');
                $(".inbox_mail_message_details").first().html(data['message_body']);
                if (data['inbox_mssg_count']) {
                    $('.inbox_mssg_count').show();
                    $('.inbox_mssg_count').text(data['inbox_mssg_count']);
                } else {
                    $('.inbox_mssg_count').hide();
                }
                if (data['starred_mssg_count']) {
                    $('.starred_mssg_count').show();
                    $('.starred_mssg_count').text(data['starred_mssg_count']);
                } else {
                    $('.starred_mssg_count').hide();
                }
                if (data['snoozed_mssg_count']) {
                    $('.snoozed_mssg_count').show();
                    $('.snoozed_mssg_count').text(data['snoozed_mssg_count']);
                } else {
                    $('.snoozed_mssg_count').hide();
                }
                if (data['counter_fd_msgs']) {
                    _.each(data['counter_fd_msgs'], function(val, index) {
                        $("#counter_fd_msg" + index).text(val);
                        if (val == '0') {
                            $("#counter_fd_msg" + index).hide();
                        } else {
                            $("#counter_fd_msg" + index).show();
                        }
                    });
                }
                self.removeLoading();
            });
        },
        _onMessageDetailsHeader: function(event) {
            var para = $('para')
            $(event.currentTarget).closest('.message').removeClass("message--open");
            $(event.currentTarget).closest('.message').css('margin-top', '0%').css('margin-bottom', '0%');
            $(event.currentTarget).parent().find('.message__details__footer_reply').hide()
            $(event.currentTarget).parent().find('.message__details__footer').show()
            $(event.currentTarget).parents().find('.reply_body_content .note-editable').html('').html(para)
            $(event.currentTarget).parents().find('.output_result').val('');
        },
        _onRightButtonExit: function(event) {
            var para = $('para')
            $(event.currentTarget).parents().find('.min-hide input:text').val('');
            $(event.currentTarget).parents().find("#compose_partner").select2('val', false);

            $(event.currentTarget).parents().find('#header-newmail .note-editable').html('');
            var clonedContent = $('#originalContent').find('.user_signature').clone();
            clonedContent.prepend('<br/>');
            $(event.currentTarget).parents().find('#header-newmail .note-editable').append(clonedContent);

            $(event.currentTarget).parents("#newmail").find('#compose_attach_result').val('');
            $(event.currentTarget).parents("ve#newmail").find('#compose_attach_result').css('padding-top', '0px')
            $("#newmail").hide();
        },
        _onDetailMessageReply: function(event) {

            $(event.currentTarget).closest('.message__details__footer').hide();
            $(event.currentTarget).closest('.message__details__footer').next().show();
            var a = $(event.currentTarget).closest('.message__details').find('.message__details__body:last').find('.body_content').find('.body_mail_id_date').find('.date_content').find('span')[0].innerHTML;
            var b = $(event.currentTarget).closest('.message__details').find('.message__details__body:last').find('.body_content').find('.body_mail_id_date').find('.message__details__body_user_name')[0].innerHTML;
            var c = $(event.currentTarget).closest('.message__details').find('.message__details__body:last').find('.body_content').find('.message__details__body__content')[0].innerHTML;
            // var wrapper= document.createElement('div');
            // wrapper.append(a[0]);
            // wrapper.append(b[0]);
            var greeting_text = $(".load_editor").summernote("code");
            var res = "<br/>" + "<br/>" + "<br/>" + greeting_text + "<br/>" + "<br/>" + "<br/>" + "<div><div dir='ltr'>" + "On " + a + " at " + b + " wrote:" + "<br/>" + "</div>" + "<blockquote style='margin:0px 0px 0px 0.8ex; padding-left:1ex'>" + "<div dir='ltr'>" + "<div>" + c + "</div>" + "</div>" + "</blockquote>" + "</div>"
            $(event.currentTarget).closest('.message__details__footer').next().find('.load_editor1').summernote('code', res);
            if (window.File && window.FileList && window.FileReader) {
                var filesInput = document.getElementsByClassName("image_src");

                for (j = 0; j < filesInput.length; j++) {
                    filesInput[j].addEventListener("change", function(event) {
                        var files = event.target.files;
                        var parentele = event.target.parentNode.nextElementSibling;

                        $(files).each(function(file) {
                            var self = this;
                            var reader = new FileReader();
                            reader.readAsDataURL(this);
                            reader.onload = function(e) {
                                var picFile = e.target;
                                var div = document.createElement("div");
                                if (self.type.match('image')) {
                                    div.innerHTML = "<span href='#' class='fa fa-times-circle'></span> <img class='thumbnail' src='" + picFile.result + "'" +
                                        "title='" + self.name + "'/>";
                                } else if (self.type === 'application/vnd.ms-excel') {
                                    div.innerHTML = "<span href='#' class='fa fa-times-circle'></span> <img class='thumbnail' src='/odoo_inbox/static/src/img/excel.png'" +
                                        "title='" + self.name + "'/>";
                                } else if (self.type === 'application/pdf') {
                                    div.innerHTML = "<span href='#' class='fa fa-times-circle'></span> <img class='thumbnail' src='/odoo_inbox/static/src/img/pdf.png'" +
                                        "title='" + self.name + "'/>";
                                } else {
                                    div.innerHTML = "<span href='#' class='fa fa-times-circle'></span> <img class='thumbnail' src='/odoo_inbox/static/src/img/zip.png'" +
                                        "title='" + self.name + "'/>";
                                }
                                parentele.appendChild(div);
                                div.children[0].addEventListener("click", function(event) {
                                    div.parentNode.removeChild(div);
                                });
                            };
                        })
                    });
                }
            } else {
                console.log("Your browser does not support File API");
            }
            var attachments = $(event.currentTarget).parents().find('.image_src').val();
            if (attachments) {
                $('.output_result').val(attachments)
            }

            $('#reply_cc_compose_partner').select2({
                ajax: {
                    url: "/mail/get_res_partners",
                    delay: 250,
                    type: "POST",
                    contentType: "application/json",
                    data: function(params) {
                        return JSON.stringify({
                            q: params.term, // search term
                            page: params.page,
                            jsonrpc: "2.0",
                            params: {
                                kwargs: {
                                    q: params.term,
                                    page: params.page,
                                },
                                q: params.term,
                                page: params.page,
                            }
                        });
                    },
                    processResults: function(data, params) {
                        // console.log(data);
                        // data = JSON.parse(data);
                        params.page = params.page || 1;
                        return {
                            results: data.result.items,
                            pagination: {
                                more: (params.page * 30) < data.total_count
                            }
                        };
                    },
                    cache: true,
                },
                width: '100%',
                placeholder: "Cc",
                allowClear: true,
                tags: true,
                createTag: function(params) {
                    var value = params.term;
                    if (self.validateEmail(value)) {
                        return {
                            id: value,
                            text: value,
                            newTag: true,
                        };
                    }
                    return null;
                },
            }).on('select2:select', function(evt) {
                if (evt.params.data.newTag) {
                    ajax.jsonRpc('/mail/partner_create', 'call', {
                        email_address: evt.params.data.text,
                    }).then(function(data) {
                        $('#reply_cc_compose_partner option[value="' + evt.params.data.text + '"]').text(data.partner_name);
                        $('#reply_cc_compose_partner option[value="' + evt.params.data.text + '"]').text(data.email);
                        $('#reply_cc_compose_partner option[value="' + evt.params.data.text + '"]').attr('value', data.partner_id);
                    });
                }
            });

            $('#reply_bcc_compose_partner').select2({
                ajax: {
                    url: "/mail/get_res_partners",
                    delay: 250,
                    type: "POST",
                    contentType: "application/json",
                    data: function(params) {
                        return JSON.stringify({
                            q: params.term, // search term
                            page: params.page,
                            jsonrpc: "2.0",
                            params: {
                                kwargs: {
                                    q: params.term,
                                    page: params.page,
                                },
                                q: params.term,
                                page: params.page,
                            }
                        });
                    },
                    processResults: function(data, params) {
                        // console.log(data);
                        // data = JSON.parse(data);
                        params.page = params.page || 1;
                        return {
                            results: data.result.items,
                            pagination: {
                                more: (params.page * 30) < data.total_count
                            }
                        };
                    },
                    cache: true,
                },
                width: '100%',
                placeholder: "Bcc",
                allowClear: true,
                tags: true,
                createTag: function(params) {
                    var value = params.term;
                    if (self.validateEmail(value)) {
                        return {
                            id: value,
                            text: value,
                            newTag: true,
                        };
                    }
                    return null;
                },
            }).on('select2:select', function(evt) {
                if (evt.params.data.newTag) {
                    ajax.jsonRpc('/mail/partner_create', 'call', {
                        email_address: evt.params.data.text,
                    }).then(function(data) {
                        $('#reply_bcc_compose_partner option[value="' + evt.params.data.text + '"]').text(data.partner_name);
                        $('#reply_bcc_compose_partner option[value="' + evt.params.data.text + '"]').text(data.email);
                        $('#reply_bcc_compose_partner option[value="' + evt.params.data.text + '"]').attr('value', data.partner_id);
                    });
                }
            });

            var self = this;
            $('#reply_compose_partner').select2({
                ajax: {
                    url: "/mail/get_res_partners",
                    delay: 250,
                    type: "POST",
                    contentType: "application/json",
                    data: function(params) {
                        return JSON.stringify({
                            q: params.term, // search term
                            page: params.page,
                            jsonrpc: "2.0",
                            params: {
                                kwargs: {
                                    q: params.term,
                                    page: params.page,
                                },
                                q: params.term,
                                page: params.page,
                            }
                        });
                    },
                    processResults: function(data, params) {
                        // console.log(data);
                        // data = JSON.parse(data);
                        params.page = params.page || 1;
                        return {
                            results: data.result.items,
                            pagination: {
                                more: (params.page * 30) < data.total_count
                            }
                        };
                    },
                    cache: true,
                },
                width: '100%',
                placeholder: "To",
                allowClear: true,
                minimumInputLength: 2,
                tags: true,
                createTag: function(params) {
                    var value = params.term;
                    if (self.validateEmail(value)) {
                        return {
                            id: value,
                            text: value,
                            newTag: true,
                        };
                    }
                    return null;
                },
            }).on('select2:select', function(evt) {
                if (evt.params && evt.params.data) {
                    const name = evt.params.data.text.split("<")[0];
                    const div = document.createElement('div')
                    div.innerHTML=", " + name
                    div.className="message__details__body_user_name"
                    document.querySelector('form .message__details_user_name').append(div)
                }
                if (evt.params.data.newTag) {
                    ajax.jsonRpc('/mail/partner_create', 'call', {
                        email_address: evt.params.data.text,
                    }).then(function(data) {
                        $('#reply_compose_partner option[value="' + evt.params.data.text + '"]').text(data.partner_name);
                        $('#reply_compose_partner option[value="' + evt.params.data.text + '"]').text(data.email);
                        $('#reply_compose_partner option[value="' + evt.params.data.text + '"]').attr('value', data.partner_id);
                    });
                }
            });
            let to_email = $('.email_from').text().replace("&gt;", "").split("&lt;")[1];
            if (!to_email)
                to_email = $('.email_from').text();
            $.ajax({
                url: "/mail/get_res_partners",
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify({
                    q: to_email, // Replace with your search term
                    page: 1, // Replace with the desired page number
                    jsonrpc: "2.0",
                    params: {
                        kwargs: {
                            q: to_email, // Same search term
                            page: 1, // Same page number
                        },
                        q: to_email, // Same search term
                        page: 1, // Same page number
                    }
                }),
                success: function(data) {
                    if (data.result.items.length)
                        $("#reply_compose_partner").select2("trigger", "select", {
                            data: data.result.items[0]
                        });
                    else {
                        $("#reply_compose_partner").select2("trigger", "select", {
                            data: {
                                text: to_email,
                                id: -1
                            }
                        });
                    }
                },
                error: function(xhr, status, error) {
                    // Handle any errors
                    console.error("Error occurred:", status, error);
                }
            });

            setTimeout(() => { $('.note-editable').focus(); }, 1000);
        },
        _onReplyDeleteButtonClick: function(event) {
            var para = $('para')
            $(event.currentTarget).parents('.message__details__footer_reply').hide();
            $(event.currentTarget).parents('.message__details__footer_reply').prev().show();
            $(event.currentTarget).parents().find('.reply_body_content .note-editable').html('').html(para);
            $(event.currentTarget).parents(".message__details__footer_reply").find('.output_result').val('');
        },
        _onStarredButtonIconClick: function(event) {
            var message = $(event.currentTarget).parent().data('message');
            if ($(event.currentTarget).hasClass('fa fa-star-o')) {
                var action = 'add'
                $(event.currentTarget).removeClass('fa fa-star-o').addClass('fa fa-star');
            } else {
                var action = 'remove'
                $(event.currentTarget).removeClass('fa fa-star').addClass('fa fa-star-o');
            }
            ajax.jsonRpc('/mail/starred/message', 'call', {
                action: action,
                message: message
            }).then(function() {
                window.location.reload();
            });
        },
        _onMarkAsDoneButtonIconClick: function(event) {
            $(event.currentTarget).css('color', 'green');
            var message = $(event.currentTarget).parent().data('message');
            var $remove = $(event.currentTarget);
            if (message) {
                return ajax.jsonRpc('/web/dataset/call_kw', 'call', {
                    model: 'mail.message',
                    method: 'set_message_done',
                    args: [message],
                    kwargs: {}
                });
            } else {
                return $.when();
            }
        },
        _onArrowClick: function(event) {
            $(".collapse", $(event.currentTarget).parents('.msg-recipients')).toggle();
        },
        _onClickButtonClosestFormSubmit: function(event) {
            $(event.currentTarget).closest('form').submit();
        },
        _onAllMessageTagApplyButtonClick: function(event) {
            var selected = [];
            $('#wrapper  input.individual:checked').each(function() {
                selected.push($(this).closest('.message__summary').data('message'));
            });
            var tag_ids = new Array();
            var this_val = $(event.currentTarget);
            var message_id = selected;
            var checked_box = $(event.currentTarget).closest('.tag_dropdown').find('input[type="checkbox"]:checked');
            $.each($(checked_box), function(key, value) {
                tag_ids.push(parseInt($(value).val()));
            });
            var create_tag_input = $(event.currentTarget).closest('ul').find('.create_tag_input').val();
            if (message_id.length) {
                if (!!create_tag_input) {
                    create_tag_input = create_tag_input;
                } else {
                    create_tag_input = false;
                }
                ajax.jsonRpc('/mail/message_tag_assign/all', 'call', {
                    message_id: message_id,
                    tag_ids: tag_ids,
                    create_tag_input: create_tag_input,
                }).then(function(data) {
                    window.location.reload();
                });
            }
        },
        _onRemoveTagClick: function(event) {
            var this_val = $(event.currentTarget);
            var tag_data = $(event.currentTarget).data();
            if (tag_data.tag && tag_data.message) {
                ajax.jsonRpc('/mail/message_tag_delete', 'call', {
                    message_id: parseInt(tag_data.message),
                    tag_id: parseInt(tag_data.tag),
                }).then(function(data) {
                    if (data.success) {
                        $('.message').find("[data-message='" + this_val.attr('data-message') + "']").closest('div.message_tag_list_details_body').html(data.message_tag_list);
                        $('.message__details__body').find('div.message_tag_list_details_body').html(data.message_tag_list);
                        $('.message__details__body').find('div.message_tag_dropdown_details').html(data.message_tag_dropdown);
                    }
                });
            }
        },
        _onTagDropDownLabelClick: function(event) {
            event.stopPropagation();
        },
        _onTagDropDownApplyButtonClick: function(event) {
            var tag_ids = new Array();
            var this_val = $(event.currentTarget);
            var message_id = $(event.currentTarget).attr('data-message');
            var checked_box = $(event.currentTarget).closest('.tag_dropdown').find('input[type="checkbox"]:checked');
            $.each($(checked_box), function(key, value) {
                tag_ids.push(parseInt($(value).val()));
            });
            var create_tag_input = $(event.currentTarget).closest('ul').find('.create_tag_input').val();
            if (message_id) {
                if (!!create_tag_input) {
                    create_tag_input = create_tag_input;
                } else {
                    create_tag_input = false;
                }
                ajax.jsonRpc('/mail/message_tag_assign', 'call', {
                    message_id: parseInt(message_id),
                    tag_ids: tag_ids,
                    create_tag_input: create_tag_input,
                }).then(function(data) {
                    if (!!data.message_tag_list) {
                        $('.message').find("[data-message='" + this_val.attr('data-message') + "']").closest('div.message_tag_list_details_body').html(data.message_tag_list);
                        $('.message__details__body').find('div.message_tag_list_details_body').html(data.message_tag_list);
                        $('.message_tag_dropdown_details').html(data.message_tag_dropdown);
                        this_val.closest('.tag_dropdown').removeClass('open');
                    }
                });
            }
        },
        _onFolderDropDownApplyButton: function(event) {
            event.stopPropagation();
        },
        _onButtonFullScreenClick: function(event) {
            if ($(event.currentTarget).closest('#newmail').hasClass('fullscreenmsger_cl')) {
                $(event.currentTarget).closest('#newmail').removeClass("fullscreenmsger_cl");
                $(event.currentTarget).find("i").removeClass('fa fa-compress').addClass('fa fa-expand');
                $(event.currentTarget).attr('title', 'Expand to full-screen');
            } else {
                $(event.currentTarget).find("i").removeClass('fa fa-expand').addClass('fa fa-compress');
                $(event.currentTarget).attr('title', 'Exit full-screen');
                $(event.currentTarget).closest('#newmail').addClass("fullscreenmsger_cl");
                $(event.currentTarget).closest('#newmail').removeClass("fix_mail_hight_cl");
                $(".button-minimize").find("i").removeClass('fa fa-window-maximize').addClass('fa fa-minus');
                $(".button-minimize").attr('title', 'Minimize');
            }
        },
        _onButtonMinimizeClick: function(event) {
            if ($(event.currentTarget).closest('#newmail').hasClass('fix_mail_hight_cl')) {
                $(event.currentTarget).closest('#newmail').removeClass("fix_mail_hight_cl");
                $(event.currentTarget).find("i").removeClass('fa fa-window-maximize').addClass('fa fa-minus');
                $(event.currentTarget).attr('title', 'Minimize');
                // $(".button-fullscreen").find("i").removeClass('fa fa-expand').addClass('fa fa-compress');
                // $(".button-fullscreen").attr('title', 'Exit full-screen');
            } else {
                $(event.currentTarget).find("i").removeClass('fa fa-minus').addClass('fa fa-window-maximize');
                $(event.currentTarget).attr('title', 'Maximize');
                $(event.currentTarget).closest('#newmail').addClass("fix_mail_hight_cl");
                $(event.currentTarget).closest('#newmail').removeClass("fullscreenmsger_cl");
                $(".button-fullscreen").find("i").removeClass('fa fa-compress').addClass('fa fa-expand');
                $(".button-fullscreen").attr('title', 'Expand to full-screen');
            }
        },
        _onOpenNewMailClick: function(event) {
            $('#forward_attach_result').remove();
            $("#newmail").show();
            if ($("#newmail").hasClass('fix_mail_hight_cl')) {
                $("#newmail").removeClass("fix_mail_hight_cl");
                $(".button-fullscreen").find("i").removeClass('fa fa-compress').addClass('fa fa-expand')
                $(".button-fullscreen").attr('title', 'Expand to full-screen');
                $(".button-minimize").find("i").removeClass('fa fa-window-maximize').addClass('fa fa-minus')
                $(".button-minimize").attr('title', 'Minimize');
            }
            if (event && $(event.currentTarget).hasClass('message_forwad open_newmail')) {
                var subject = $(event.currentTarget).closest('.message__details').find('.main_subject').data('subject');

                var e_from = $(event.currentTarget).closest('.message__details').find('.address_dropdown table .email_from')[0].innerHTML;
                var e_date = $(event.currentTarget).closest('.message__details').find('.message__details__body:last').find('.body_content').find('.body_mail_id_date').find('.date_content').find('span')[0].innerHTML;
                var e_to = '';
                if ($(event.currentTarget).closest('.message__details').find('.address_dropdown table .email_to').length > 0) {
                    var e_to = $(event.currentTarget).closest('.message__details').find('.address_dropdown table .email_to')[0].innerHTML;
                }
                var e_body = $(event.currentTarget).closest('.message__details').find('.message__details__body:last').find('.body_content').find('.message__details__body__content')[0].innerHTML;
                var mssg_body = "<br/>" + "<br/>" + "---------- Forwarded message ---------" + "<br/>" + "From: " + "<b>" + e_from + "</b>" + "<br/>" + "Date: " + e_date + "<br/>" + "Subject: " + subject + "<br/>" + "To: " + "<b>" + e_to + "</b>" + "<br/>" + "<br/>" + e_body + "<br/>"

                var attachments = $(event.currentTarget).parent().parent().parent().find('.image_src').val()

                if (subject) {
                    $('#gmail_compose_subject').val(subject);
                } else {
                    $('#gmail_compose_subject').val('');
                }
                if (mssg_body) {
                    var greeting_text = $(".load_editor").summernote("code");
                    $(".load_editor").summernote("code", "<br/ > <br /> <br/>" + greeting_text + "<br>" + mssg_body);
                }
                if (attachments) {
                    $('#compose_attach_result').val(attachments)
                }

                if ($(event.currentTarget).hasClass('message_forwad')) {
                    const links = $('.attachment_content a');
                    let ids = [];
                    for (const link of links) {
                        const split = link.getAttribute('href').split('/')
                        ids.push(split[split.length - 2]);
                    }
                    const newInput = $('<input>', {
                        type: 'hidden',
                        id: 'forward_attachments',
                        name: 'forward_attachments',
                    });
                    newInput.value = ids.join(',');
                    $('#newmail form').append(newInput);
                    $('#forward_attachments').val(ids.join(','))
                }
            }

            $('.note-editable').focus();
        },
        _onMailOptionSelectAll: function(event) {
            $(".individual").prop("checked", $(event.currentTarget).prop("checked"));
            if ($(event.currentTarget).is(":checked")) {
                $(".all_snooze_bttn").show();
                $(".all_move_to_bttn").show();
                $(".all_mssg_to_trash").show();
                $(".all_mssg_to_tag").show();
                $(".all_mssg_to_done").show();
            } else {
                $(".all_snooze_bttn").hide();
                $(".all_move_to_bttn").hide();
                $(".all_mssg_to_trash").hide();
                $(".all_mssg_to_tag").hide();
                $(".all_mssg_to_done").hide();
            }
        },
        _onIndividualCheckBoxClick: function(event) {
            var checkCount = $(".individual:checked").length;
            if ($(event.currentTarget).is(":checked") || checkCount > 0) {
                $(".all_snooze_bttn").show();
                $(".all_move_to_bttn").show();
                $(".all_mssg_to_trash").show();
                $(".all_mssg_to_tag").show();
                $(".all_mssg_to_done").show();
            } else {
                $(".all_snooze_bttn").hide();
                $(".all_move_to_bttn").hide();
                $(".all_mssg_to_trash").hide();
                $(".all_mssg_to_tag").hide();
                $(".all_mssg_to_done").hide();
            }
        },
        _onMoveFolderClick: function(event) {
            var selected = [];
            $('#wrapper  input.individual:checked').each(function() {
                selected.push($(this).closest('.message__summary').data('message'));
            });
            var folder_id = $(event.currentTarget).data('folder_id');
            var vals = location.pathname.split('/');
            ajax.jsonRpc('/mail/'+(isInteger(vals[2])?vals[2]:vals[3])+'/all_move_to_folder', 'call', {
                messg_ids: selected,
                folder_id: folder_id,
            }).then(function() {
                window.location.reload();
            });
        },
        _onAllMessageStarredClick: function(event) {
            var mssg_starred = [];
            $('.message__summary').each(function() {
                mssg_starred.push($(this).data('message'));
            });

            ajax.jsonRpc('/mail/all_mssg_starred', 'call', {
                action: 'add',
                messg_ids: mssg_starred,
            }).then(function() {
                window.location.reload();
            });
        },
        _onAllMessageUnStarredClick: function(event) {
            var mssg_unstarred = [];
            $('.message__summary').each(function() {
                mssg_unstarred.push($(this).data('message'));
            });

            ajax.jsonRpc('/mail/all_mssg_unstarred', 'call', {
                action: 'remove',
                messg_ids: mssg_unstarred,
            }).then(function() {
                window.location.reload();
            });
        },
        _onAllMessageUnReadClick: function(event) {
            var mssg_unread = [];
            $('.message__summary').each(function() {
                mssg_unread.push($(this).data('message'));
            });

            ajax.jsonRpc('/mail/all_mssg_unread', 'call', {
                messg_ids: mssg_unread,
            }).then(function() {
                window.location.reload();
            });
        },
        _onAllMessageReadClick: function(event) {
            var mssg_read = [];
            $('.message__summary').each(function() {
                mssg_read.push($(this).data('message'));
            });

            ajax.jsonRpc('/mail/all_mssg_read', 'call', {
                messg_ids: mssg_read,
            }).then(function() {
                window.location.reload();
            });
        },
        _onSnoozeChildMenuAClick: function(event) {
            var mssg_snooze = [];
            $(event.currentTarget).parents().find('input.individual:checked').each(function() {
                mssg_snooze.push($(this).closest('.message__summary').data('message'));
            });
            var your_time;
            if ($(event.currentTarget).hasClass('snooze_later_today')) {
                your_time = 'today'
            }
            if ($(event.currentTarget).hasClass('snooze_tomorrow')) {
                your_time = 'tomorrow'
            }
            if ($(event.currentTarget).hasClass('snooze_nexweek')) {
                your_time = 'nexweek'
            }
            ajax.jsonRpc('/mail/all_mssg_snoozed', 'call', {
                mssg_snooze: mssg_snooze,
                your_time: your_time,
            }).then(function() {
                window.location.reload();
            });
        },
        _onSnoozeDateSubmitClick: function(event) {
            var mssg_snooze = [];
            $(event.currentTarget).parents().find('input.individual:checked').each(function() {
                mssg_snooze.push($(this).closest('.message__summary').data('message'));
            });
            var snooze_datepicker = $('#snoozedatePicker').val();
            ajax.jsonRpc('/mail/all_mssg_snoozed_submit', 'call', {
                mssg_snooze: mssg_snooze,
                snooze_date: snooze_datepicker,
            }).then(function() {
                window.location.reload();
            });
        },

        _onAllMessageToTrash: function(event) {
            var mssg_trash = [];
            $(event.currentTarget).parents().find('input.individual:checked').each(function() {
                mssg_trash.push($(this).closest('.message__summary').data('message'));
            });
            const vals = location.pathname.split('/');
            ajax.jsonRpc('/mail/'+(isInteger(vals[2])?vals[2]:vals[3])+'/all_mssg_trash', 'call', {
                messg_ids: mssg_trash,
            }).then(function() {
                window.location.reload();
            });
        },
        _onAllMessageToDone: function(event) {
            var mssg_done = [];
            $('#wrapper  input.individual:checked').each(function() {
                mssg_done.push($(this).closest('.message__summary').data('message'));
            });
            ajax.jsonRpc('/mail/all_mssg_done', 'call', {
                messg_ids: mssg_done,
            }).then(function() {
                window.location.reload();
            });
        },
        _onChangeDocumentModel: function(event) {
            var model_name = $(event.currentTarget).val();
            $('#document_model_records').removeClass('d-none');
            $('#document_model_record_followers').html('');
            $('#document_model_record_followers').addClass('d-none');
            $('#document_model_records').html('<option value="0">Select record</option>');
            $('#document_compose_mail_template').html('<option value="0">Select template</option>');
            $(".load_editor").summernote("code", '');
            ajax.jsonRpc('/mail/get_document_records', 'call', {
                document_model: model_name,
            }).then(function(records) {
                if (records) {
                    var option_html = '';
                    _.each(records, function(record) {
                        option_html += '<option value=' + record[0] + '>' + record[1] + '</option>';
                    });
                    $('#document_model_records').append(option_html);
                }
            });
        },
        _getMailTemplates: function(model_name) {
            var self = this;
            $('#document_compose_mail_template').html('<option value="0">Select template</option>');
            ajax.jsonRpc('/mail/get_mail_templates', 'call', {
                document_model: model_name,
            }).then(function(records) {
                if (records) {
                    var option_html = '';
                    _.each(records, function(record) {
                        option_html += '<option value=' + record['id'] + '>' + record['name'] + '</option>';
                    });
                    $('#document_compose_mail_template').append(option_html);
                    $('.compose_select_templates').removeClass('d-none');
                    $('#btn_compose_save_template').removeClass('d-none');
                }
            });
        },
        _onChangeDocumentRecord: function(event) {
            var self = this;
            var model_name = $('#document_model').val();
            var res_id = $(event.currentTarget).val();
            $('#document_model_record_followers').removeClass('d-none');
            $('#document_model_record_followers').html('');
            $('#document_compose_mail_template').html('<option value="0">Select template</option>');
            $(".load_editor").summernote("code", '');
            if (model_name && res_id) {
                ajax.jsonRpc('/mail/get_document_followers', 'call', {
                    document_model: model_name,
                    res_id: res_id,
                }).then(function(records) {
                    if (records && records.length >= 1) {
                        var follower_html = '<span>Followers of the document: </span>';
                        _.each(records, function(record) {
                            follower_html += '<span class="badge badge-success ml-1">' + record['name'] + '</span>';
                        });
                        $('#document_model_record_followers').append(follower_html);
                        $('#compose_partner').attr('required', "false");
                    }
                });
                self._getMailTemplates(model_name);

            } else {
                self._getMailTemplates('inbox.mail.template');
            }
        },
        _onChangeDocumentMailTemplate: function(event) {
            var self = this;
            var res_id = $('#document_model_records').val();
            var mail_template_id = $(event.currentTarget).val();
            self.displayLoading(true);
            ajax.jsonRpc('/mail/get_mail_template_body', 'call', {
                mail_template_id: mail_template_id,
                res_id: res_id,
            }).then(function(datas) {
                if (datas) {
                    if (datas['subject']) {
                        $('#gmail_compose_subject').val(datas['subject']);
                    } else {
                        $('#gmail_compose_subject').val('');
                    }
                    if (datas['body_html']) {
                        $(".load_editor").summernote("code", datas['body_html']);
                    }
                }
                self.removeLoading();
            });
        },
        _onClickComposeSaveTemplate: function(event) {
            var model_name = $('#document_model').val() || false;
            var subject = $('#gmail_compose_subject').val();
            var body_html = $(".load_editor").summernote("code");
            if (body_html) {
                ajax.jsonRpc('/mail/create_mail_template', 'call', {
                    model_name: model_name,
                    body_html: body_html,
                    subject: subject,
                }).then(function(datas) {});
            }
        },
        _onClickInboxThemeImage: function(event) {
            var self = this;
            var value = {}
            var image = $(event.currentTarget).data('src');
            $('.odoo_inbox_page').attr('style', 'background-image: url(' + image + ');background-color: transparent;background-size: cover;background-repeat: no-repeat;background-position: center;background-attachment: fixed;');
            value['inbox_theme_backgroud_image'] = image;
            value['inbox_theme_backgroud_color'] = false;
            rpc.query({
                model: 'res.users',
                method: 'set_inbox_setting_user',
                args: [session.user_id],
                kwargs: value,
            }).then(function(res) {});
        },
        _onClickInboxThemeColor: function(event) {
            var self = this;
            var value = {}
            var color = $(event.currentTarget).data('src');
            $('.odoo_inbox_page').attr('style', 'background-color: ' + color + ';background-image: none;');
            value['inbox_theme_backgroud_color'] = color;
            value['inbox_theme_backgroud_image'] = false;
            rpc.query({
                model: 'res.users',
                method: 'set_inbox_setting_user',
                args: [session.user_id],
                kwargs: value,
            }).then(function(res) {});
        },
    });

    $( "#newmail" ).draggable({ handle: ".title" }).resizable();
});