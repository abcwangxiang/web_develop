function initialize_activity(){
    $("a[id^='tool_activity_']").on('click', function(){
        var activity_a = $(this);
        var id = activity_a.attr("id"); //..id
        activity = id.replace("tool_activity_","");
        //love.fadeOut(300); //....
        $.ajax({
            type:"GET",
            url:"/Tool_Activity",
            data:"activity="+activity,
            cache:false, //......
            success:function(res){
                if(res.res=="success"){
                }
                else{
                    alert(res.res);
                }
            }
        });
    })
}
